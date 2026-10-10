from __future__ import annotations

from typing import TYPE_CHECKING, Type

from dcs import Point

from game.ato.flighttype import FlightType
from game.utils import Distance, Heading, feet, meters, nautical_miles
from .ibuilder import IBuilder
from .patrolling import (
    PatrollingLayout,
    step_back_from_threat,
    support_spawns_on_station,
)
from .refuelingflightplan import RefuelingFlightPlan
from .waypointbuilder import WaypointBuilder

if TYPE_CHECKING:
    from ..flightwaypoint import FlightWaypoint


class TheaterRefuelingFlightPlan(RefuelingFlightPlan):
    @property
    def starts_on_station(self) -> bool:
        return support_spawns_on_station(self.flight)

    @staticmethod
    def builder_type() -> Type[Builder]:
        return Builder


#: How far apart consecutive theater tankers sit, measured back from the threat.
#:
#: A coalition flying both boom and probe receivers gets one tanker of each, and
#: without this they would be handed the same racetrack -- two orbits in the same
#: airspace at the same altitude.
TANKER_ORBIT_SPACING = nautical_miles(15)

#: The racetrack's length, across the threat axis. Upstream's value. A four-corner
#: box flew here from 2026-09-28 to 2026-10-09 and never levelled out with a jet
#: on the boom; see docs/dev/design/retlab-tanker-box-notes.md before trying again.
TANKER_TRACK_LENGTH = nautical_miles(40)

#: Vertical gap between every theater tanker on a side. The spacing above only
#: separates tankers in one package; two packages' tracks can still cross.
TANKER_ALTITUDE_SEPARATION = feet(2000)


def deconflicted_altitude(
    preferred: Distance,
    taken: list[Distance],
    floor: Distance,
    ceiling: Distance,
) -> Distance:
    """The altitude nearest ``preferred``, higher first, clear of ``taken``.

    Steps in ``TANKER_ALTITUDE_SEPARATION``; ``preferred`` when no step fits.
    """
    gap = TANKER_ALTITUDE_SEPARATION.feet
    for step in range(8):
        for sign in (1, -1) if step else (1,):
            candidate = feet(preferred.feet + sign * step * gap)
            if not floor <= candidate <= ceiling:
                continue
            if all(abs(candidate.feet - other.feet) > gap - 1 for other in taken):
                return candidate
    return preferred


def move_track(flight_plan: object, waypoint: FlightWaypoint, to: Point) -> bool:
    """Drag a theater tanker's racetrack on the map.

    The start point moves the whole track; the end point swings it around the
    start at its own length. False for any other point, which the caller moves
    alone.
    """
    if not isinstance(flight_plan, TheaterRefuelingFlightPlan):
        return False
    start, end = flight_plan.layout.patrol_start, flight_plan.layout.patrol_end
    if waypoint is start:
        dx, dy = to.x - start.position.x, to.y - start.position.y
        for point in (start, end):
            point.position = point.position.new_in_same_map(
                point.position.x + dx, point.position.y + dy
            )
        return True
    if waypoint is end:
        length = start.position.distance_to_point(end.position)
        if length < 1 or start.position.distance_to_point(to) < 1:
            return True
        end.position = start.position.point_from_heading(
            start.position.heading_between_point(to), length
        )
        return True
    return False


def track_drag_note(flight_plan: object, waypoint: FlightWaypoint) -> str:
    """What dragging this point does, for the map tooltip; empty off the track."""
    if not isinstance(flight_plan, TheaterRefuelingFlightPlan):
        return ""
    if waypoint is flight_plan.layout.patrol_start:
        return "Drag: moves the whole track"
    if waypoint is flight_plan.layout.patrol_end:
        return "Drag: swings the track around its start"
    return ""


class Builder(IBuilder[TheaterRefuelingFlightPlan, PatrollingLayout]):
    def _orbit_index(self) -> int:
        """This tanker's place in its package, so several do not stack up.

        Identity, not equality: ``list.index`` would match the first flight that
        merely compares equal, which is how two tankers end up sharing a slot.
        """
        index = 0
        for flight in self.package.flights:
            if flight is self.flight:
                return index
            if flight.flight_type is FlightType.REFUELING:
                index += 1
        return 0

    def _other_tanker_altitudes(self) -> list[Distance]:
        altitudes = []
        for package in self.coalition.ato.packages:
            for flight in package.flights:
                if (
                    flight is self.flight
                    or flight.flight_type is not FlightType.REFUELING
                ):
                    continue
                plan = flight.laid_out_flight_plan
                if isinstance(plan, TheaterRefuelingFlightPlan):
                    altitudes.append(plan.layout.patrol_start.alt)
        return altitudes

    def layout(self) -> PatrollingLayout:
        racetrack_half_distance = TANKER_TRACK_LENGTH.meters / 2

        location = self.package.target

        closest_boundary = self.threat_zones.closest_boundary(location.position)
        heading_to_threat_boundary = Heading.from_degrees(
            location.position.heading_between_point(closest_boundary)
        )
        distance_to_threat = meters(
            location.position.distance_to_point(closest_boundary)
        )
        orbit_heading = heading_to_threat_boundary

        # Station 70nm outside the threat zone.
        threat_buffer = nautical_miles(
            self.coalition.game.settings.tanker_threat_buffer_min_distance
        )
        threatened = self.threat_zones.threatened(location.position)
        if threatened:
            orbit_distance = distance_to_threat + threat_buffer
        else:
            orbit_distance = distance_to_threat - threat_buffer

        # Each further tanker sits another step back from the threat. Backwards
        # rather than forwards so an extra tanker can never be pushed into the
        # threat zone the buffer above just cleared -- which for a threatened
        # anchor means further past the edge, not back toward it.
        orbit_distance = step_back_from_threat(
            orbit_distance,
            threatened=threatened,
            step=TANKER_ORBIT_SPACING * self._orbit_index(),
        )

        racetrack_center = location.position.point_from_heading(
            orbit_heading.degrees, orbit_distance.meters
        )

        racetrack_start = racetrack_center.point_from_heading(
            orbit_heading.right.degrees, racetrack_half_distance
        )

        racetrack_end = racetrack_center.point_from_heading(
            orbit_heading.left.degrees, racetrack_half_distance
        )

        builder = WaypointBuilder(self.flight)
        altitude = deconflicted_altitude(
            builder.get_patrol_altitude,
            self._other_tanker_altitudes(),
            self.coalition.doctrine.min_combat_altitude,
            self.coalition.doctrine.max_combat_altitude,
        )
        racetrack = builder.race_track(racetrack_start, racetrack_end, altitude)

        return PatrollingLayout(
            departure=builder.takeoff(self.flight.departure),
            nav_to=builder.nav_path(
                self.flight.departure.position, racetrack_start, altitude
            ),
            nav_from=builder.nav_path(
                racetrack_end, self.flight.arrival.position, altitude
            ),
            patrol_start=racetrack[0],
            patrol_end=racetrack[1],
            arrival=builder.land(self.flight.arrival),
            divert=builder.divert(self.flight.divert),
            bullseye=builder.bullseye(),
            custom_waypoints=list(),
        )

    def build(self, dump_debug_info: bool = False) -> TheaterRefuelingFlightPlan:
        return TheaterRefuelingFlightPlan(self.flight, self.layout())
