from __future__ import annotations

from datetime import timedelta
from typing import Callable, Type

from dcs import Point

from game.ato.flightplans.ibuilder import IBuilder
from game.ato.flightplans.patrolling import (
    PatrollingFlightPlan,
    PatrollingLayout,
    slide_clear_of_neutral_airspace,
    step_back_from_threat,
    support_spawns_on_station,
)
from game.ato.flightplans.waypointbuilder import WaypointBuilder
from game.ato.flighttype import FlightType
from game.utils import Distance, Heading, Speed, knots, meters, nautical_miles

#: How far apart consecutive AEW&C on one station sit, measured back from the
#: threat. Wider than the tanker's 15 NM: on test 36 an E-3A flew 13.8 km off its
#: leg centreline, so two tracks need about 15 NM to keep the flown paths apart,
#: and an E-3A's drawn box is 15.6 NM wide.
AEWC_ORBIT_SPACING = nautical_miles(20)


class AewcFlightPlan(PatrollingFlightPlan[PatrollingLayout]):
    @property
    def starts_on_station(self) -> bool:
        # JAMMING shares this plan and is not a support flight the setting names.
        return self.flight.flight_type is FlightType.AEWC and support_spawns_on_station(
            self.flight
        )

    @property
    def patrol_duration(self) -> timedelta:
        return self.flight.coalition.game.settings.desired_awacs_mission_duration

    @property
    def patrol_speed(self) -> Speed:
        altitude = self.layout.patrol_start.alt
        if self.flight.unit_type.preferred_patrol_speed(altitude) is not None:
            return self.flight.unit_type.preferred_patrol_speed(altitude)
        return knots(390)

    @property
    def engagement_distance(self) -> Distance:
        # TODO: Factor out a common base of the combat and non-combat race-tracks.
        # No harm in setting this, but we ought to clean up a bit.
        return meters(0)

    @staticmethod
    def builder_type() -> Type[Builder]:
        return Builder


class Builder(IBuilder[AewcFlightPlan, PatrollingLayout]):
    def _peer_orbit_centres(self) -> list[Point]:
        """Where the other AEW&C on this station already orbit.

        Read from the plans they already have, never built here: a peer laid out
        earlier keeps its orbit until something lays it out again, so its real
        position is what a new orbit has to avoid, not its place in any order.
        """
        target = self.package.target
        packages = [p for p in self.coalition.ato.packages if p.target is target]
        if not any(p is self.package for p in packages):
            packages.append(self.package)
        centres = []
        for package in packages:
            for flight in package.flights:
                if flight is self.flight or flight.flight_type is not FlightType.AEWC:
                    continue
                layout = getattr(flight.laid_out_flight_plan, "layout", None)
                start = getattr(layout, "patrol_start", None)
                end = getattr(layout, "patrol_end", None)
                if start is not None and end is not None:
                    centres.append(start.position.midpoint(end.position))
        return centres

    def _orbit_slot(self, centre_for_slot: Callable[[int], Point]) -> int:
        """The lowest slot whose orbit is clear of every AEW&C already on station.

        Tested against where the others actually are rather than counted by order:
        counting collided whenever an AWACS was added to an earlier package, or one
        was deleted and another fragged, because the ones already laid out never
        move. JAMMING shares this builder and always takes 0.
        """
        if self.flight.flight_type is not FlightType.AEWC:
            return 0
        taken = self._peer_orbit_centres()
        clear_m = AEWC_ORBIT_SPACING.meters / 2
        # n orbits can block at most n slots, so one of the first n + 1 is free.
        for slot in range(len(taken) + 1):
            centre = centre_for_slot(slot)
            if all(centre.distance_to_point(t) >= clear_m for t in taken):
                return slot
        return len(taken)

    def layout(self) -> PatrollingLayout:
        racetrack_half_distance = nautical_miles(30).meters

        location = self.package.target

        closest_boundary = self.threat_zones.closest_boundary(location.position)
        heading_to_threat_boundary = Heading.from_degrees(
            location.position.heading_between_point(closest_boundary)
        )
        distance_to_threat = meters(
            location.position.distance_to_point(closest_boundary)
        )
        orbit_heading = heading_to_threat_boundary

        # Station 80nm outside the threat zone.
        threat_buffer = nautical_miles(
            self.coalition.game.settings.aewc_threat_buffer_min_distance
        )
        threatened = self.threat_zones.threatened(location.position)
        if threatened:
            orbit_distance = distance_to_threat + threat_buffer
        else:
            orbit_distance = distance_to_threat - threat_buffer

        # Two AEW&C on one target would fly the identical racetrack. Each takes the
        # nearest free step back from the threat (the tanker's pattern); the sideways
        # spread reverted 2026-08-09 half-overlapped. See retlab-features.md §6.
        def centre_for_slot(slot: int) -> Point:
            distance = step_back_from_threat(
                orbit_distance, threatened=threatened, step=AEWC_ORBIT_SPACING * slot
            )
            return location.position.point_from_heading(
                orbit_heading.degrees, distance.meters
            )

        racetrack_center = centre_for_slot(self._orbit_slot(centre_for_slot))

        racetrack_start = racetrack_center.point_from_heading(
            orbit_heading.right.degrees, racetrack_half_distance
        )

        racetrack_end = racetrack_center.point_from_heading(
            orbit_heading.left.degrees, racetrack_half_distance
        )
        racetrack_start, racetrack_end = slide_clear_of_neutral_airspace(
            racetrack_start, racetrack_end, self.coalition, self.threat_zones
        )

        builder = WaypointBuilder(self.flight)

        altitude = builder.get_patrol_altitude

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

    def build(self, dump_debug_info: bool = False) -> AewcFlightPlan:
        return AewcFlightPlan(self.flight, self.layout())
