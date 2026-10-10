from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, TYPE_CHECKING, TypeGuard, TypeVar

from game.ato.flightplans.standard import StandardFlightPlan, StandardLayout
from game.ato.flightwaypointtype import FlightWaypointType
from game.ato.starttype import StartType
from game.ato.tankeravailability import tanking_time
from game.typeguard import self_type_guard
from game.utils import Distance, Speed, meters, nautical_miles
from .uizonedisplay import UiZone, UiZoneDisplay

if TYPE_CHECKING:
    from dcs import Point

    from ..flightwaypoint import FlightWaypoint
    from .flightplan import FlightPlan


@dataclass
class PatrollingLayout(StandardLayout):
    patrol_start: FlightWaypoint
    patrol_end: FlightWaypoint

    def iter_waypoints(self) -> Iterator[FlightWaypoint]:
        yield self.departure
        yield from self.nav_to
        yield self.patrol_start
        yield self.patrol_end
        yield from self.nav_from
        yield self.arrival
        if self.divert is not None:
            yield self.divert
        yield self.bullseye
        yield from self.custom_waypoints


LayoutT = TypeVar("LayoutT", bound=PatrollingLayout)

# What a ground-started flight needs before it can be on station at altitude: DCS
# AI levels off until the last wingman is airborne (about 2 minutes), then climbs.
# The rate errs slow so the flight is early, not late (DM call 2026-10-09).
JOIN_UP_TIME = timedelta(minutes=2)
CLIMB_RATE_FT_PER_MIN = 3000.0


def climb_out_time(departure: FlightWaypoint, first: FlightWaypoint) -> timedelta:
    """Join-up plus the climb from the field to the first waypoint's altitude."""
    gain_ft = max(first.alt.feet - departure.alt.feet, 0.0)
    return JOIN_UP_TIME + timedelta(minutes=gain_ft / CLIMB_RATE_FT_PER_MIN)


def support_spawns_on_station(flight: Any) -> bool:
    """True for an AI support flight the air-start setting put in the air.

    The setting promises on station from mission start. Spawned over its own
    field instead, a Kola A-50 took 31 minutes to reach a track 190 NM away
    (2026-10-10), so these spawn on the track and their route out costs no time.
    """
    if getattr(flight, "start_type", None) is not StartType.IN_FLIGHT:
        return False
    if flight.client_count:
        return False
    return bool(flight.coalition.game.settings.support_air_start)


def step_back_from_threat(
    orbit_distance: Distance, *, threatened: bool, step: Distance
) -> Distance:
    """Move a support orbit's centre `step` further from the threat.

    The centre lies on the line from the anchor toward the nearest threat edge. A
    clear anchor puts it short of the edge, so back is toward the anchor; a
    threatened anchor puts it past the edge, so back is further past. Subtracting in
    both cases walked a threatened anchor's extra orbits toward the zone.
    """
    return orbit_distance + step if threatened else orbit_distance - step


#: Room a support track keeps from a neutral border. The turn at each end is
#: flown outside the two points: an E-3A flew 7.5 NM off its leg (test 36).
NEUTRAL_BORDER_MARGIN = nautical_miles(8)
NEUTRAL_SLIDE_LIMIT = nautical_miles(60)


def _airspace_closed_to(coalition: Any) -> list[Any]:
    """Borders of the countries that would intercept this side (§98)."""
    game = getattr(coalition, "game", None)
    theater = getattr(game, "theater", None)
    zones = getattr(theater, "neutral_border_zones", None)
    if not zones or not getattr(game.settings, "neutral_border_defense", False):
        return []
    from shapely.geometry import Polygon

    is_blue = coalition.player.is_blue
    return [
        Polygon(zone.border).buffer(0)
        for zone in zones
        if len(zone.border) >= 3 and zone.enforces_against(theater, is_blue)
    ]


def slide_clear_of_neutral_airspace(
    start: Point, end: Point, coalition: Any, threat_zones: Any
) -> tuple[Point, Point]:
    """Slide a support track along its own length, out of neutral airspace.

    The smallest move either way that clears it, never into a threat zone the
    track was clear of. Along the track rather than back toward the anchor: on
    Kola the line home runs through Finland, so back needed 110-120 NM where
    along needed 5 and 22 (2026-10-10). Unchanged when nothing in reach is clear.
    """
    closed = _airspace_closed_to(coalition)
    if not closed:
        return start, end
    from shapely.geometry import LineString

    def clear(a: Point, b: Point) -> bool:
        corridor = LineString([(a.x, a.y), (b.x, b.y)]).buffer(
            NEUTRAL_BORDER_MARGIN.meters
        )
        return not any(corridor.intersects(country) for country in closed)

    if clear(start, end):
        return start, end
    was_threatened = threat_zones.threatened(start) or threat_zones.threatened(end)
    along = end.heading_between_point(start)
    step = nautical_miles(1).meters
    for count in range(1, int(NEUTRAL_SLIDE_LIMIT.nautical_miles) + 1):
        for direction in (1, -1):
            move = direction * count * step
            a = start.point_from_heading(along, move)
            b = end.point_from_heading(along, move)
            if not clear(a, b):
                continue
            if not was_threatened and (
                threat_zones.threatened(a) or threat_zones.threatened(b)
            ):
                continue
            return a, b
    return start, end


class PatrollingFlightPlan(StandardFlightPlan[LayoutT], UiZoneDisplay, ABC):
    @property
    @abstractmethod
    def patrol_duration(self) -> timedelta:
        """Maximum time to remain on station."""

    @property
    @abstractmethod
    def patrol_speed(self) -> Speed:
        """Racetrack speed TAS."""

    @property
    @abstractmethod
    def engagement_distance(self) -> Distance:
        """The maximum engagement distance.

        The engagement range of any Search Then Engage task, or the radius of a Search
        Then Engage in Zone task. Any enemies of the appropriate type for this mission
        within this range of the flight's current position (or the center of the zone)
        will be engaged by the flight.
        """

    @property
    def starts_on_station(self) -> bool:
        """Whether the flight spawns on its track rather than flying out to it."""
        return False

    def _leads_to_station(self, waypoint: FlightWaypoint) -> bool:
        if waypoint is self.layout.patrol_start:
            return True
        return any(waypoint is nav for nav in self.layout.nav_to)

    def travel_time_between_waypoints(
        self, a: FlightWaypoint, b: FlightWaypoint
    ) -> timedelta:
        if self.starts_on_station and self._leads_to_station(b):
            return timedelta()
        return super().travel_time_between_waypoints(a, b)

    @property
    def patrol_start_time(self) -> datetime:
        return self.tot

    @property
    def patrol_end_time(self) -> datetime:
        # TODO: This is currently wrong for CAS.
        # CAS missions end when they're winchester or bingo. We need to
        # configure push tasks for the escorts rather than relying on timing.
        return self.patrol_start_time + self.patrol_duration

    def tot_for_waypoint(self, waypoint: FlightWaypoint) -> datetime | None:
        if waypoint == self.layout.patrol_start:
            return self.patrol_start_time
        refuel = getattr(self.layout, "pre_push_refuel", None)
        if refuel is not None and waypoint is refuel:
            legs = [refuel, *self.layout.nav_to, self.layout.patrol_start]
            to_station = sum(
                (
                    self.total_time_between_waypoints(a, b)
                    for a, b in zip(legs, legs[1:])
                ),
                timedelta(),
            )
            return self.patrol_start_time - to_station
        return None

    def depart_time_for_waypoint(self, waypoint: FlightWaypoint) -> datetime | None:
        if waypoint == self.layout.patrol_end:
            return self.patrol_end_time
        return None

    def total_time_between_waypoints(
        self, a: FlightWaypoint, b: FlightWaypoint
    ) -> timedelta:
        # The patrol_start -> patrol_end leg is on-station time, not travel: the flight
        # orbits between the two points for patrol_duration (so patrol_end_time =
        # patrol_start_time + patrol_duration). Schedules chained leg-by-leg -- the manual
        # ToT cascade and the kneeboard ETAs -- sum this method per leg, so without this
        # the loiter collapses to flight time and every later waypoint shifts early.
        if a is self.layout.patrol_start and b is self.layout.patrol_end:
            return self.patrol_duration
        total = super().total_time_between_waypoints(a, b)
        if a is getattr(self.layout, "pre_push_refuel", None):
            return total + tanking_time(self.flight)
        if self._climbs_out_on(a):
            # Distance over speed puts a CAP over its own field on station seconds
            # after takeoff; the leg out of the field is never shorter than the climb.
            return max(total, climb_out_time(a, b))
        return total

    def _climbs_out_on(self, a: FlightWaypoint) -> bool:
        return (
            a is self.layout.departure
            and a.waypoint_type is FlightWaypointType.TAKEOFF
            and getattr(self.flight, "start_type", None) is not StartType.IN_FLIGHT
        )

    def fuel_burn_distance_between_points(
        self, a: FlightWaypoint, b: FlightWaypoint
    ) -> Distance:
        # The patrol_start -> patrol_end leg is flown as laps of the racetrack for
        # patrol_duration, not one straight transit, so the fuel model charges the
        # distance actually covered on station (never less than the track itself).
        # Without this the whole on-station burn -- most of a CAP's gas -- was
        # missing from every fuel consumer (kneeboard ladder, RTB margin, sim).
        if a is self.layout.patrol_start and b is self.layout.patrol_end:
            hours = self.patrol_duration.total_seconds() / 3600.0
            laps = nautical_miles(self.patrol_speed.knots * hours)
            return max(laps, super().fuel_burn_distance_between_points(a, b))
        if self.starts_on_station and self._leads_to_station(b):
            return meters(0)
        return super().fuel_burn_distance_between_points(a, b)

    def takeoff_time(self) -> datetime:
        return self.patrol_start_time - self._travel_time_to_waypoint(self.tot_waypoint)

    @property
    def package_speed_waypoints(self) -> set[FlightWaypoint]:
        return {self.layout.patrol_start, self.layout.patrol_end}

    @property
    def tot_waypoint(self) -> FlightWaypoint:
        return self.layout.patrol_start

    @property
    def mission_begin_on_station_time(self) -> datetime | None:
        return self.patrol_start_time

    @property
    def mission_departure_time(self) -> datetime:
        return self.patrol_end_time

    @self_type_guard
    def is_patrol(
        self, flight_plan: FlightPlan[Any]
    ) -> TypeGuard[PatrollingFlightPlan[Any]]:
        return True

    def ui_zone(self) -> UiZone:
        return UiZone(
            [self.layout.patrol_start.position, self.layout.patrol_end.position],
            self.engagement_distance,
        )
