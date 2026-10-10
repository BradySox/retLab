from __future__ import annotations

from datetime import timedelta
from typing import Any, Type

from game.ato.flightplans.ibuilder import IBuilder
from game.ato.flightplans.waypointbuilder import WaypointBuilder
from .patrolling import PatrollingLayout
from .refuelingflightplan import RefuelingFlightPlan
from .. import FlightWaypoint
from ...utils import knots

#: The setting's limit went from 150 to 300 minutes for theater tankers
#: (2026-10-10). The recovery station sits 20 kt times the minutes from the boat,
#: so the old limit still bounds it at 50 NM.
RECOVERY_STATION_TIME_CAP = timedelta(minutes=150)


def recovery_station_time(settings: Any) -> timedelta:
    return min(settings.desired_tanker_on_station_time, RECOVERY_STATION_TIME_CAP)


class RecoveryTankerFlightPlan(RefuelingFlightPlan):
    honors_orbit_speed = False

    @staticmethod
    def builder_type() -> Type[Builder]:
        return Builder

    @property
    def tot_waypoint(self) -> FlightWaypoint:
        return self.layout.departure


class Builder(IBuilder[RecoveryTankerFlightPlan, PatrollingLayout]):
    def layout(self) -> PatrollingLayout:

        builder = WaypointBuilder(self.flight)
        altitude = builder.get_patrol_altitude

        station_time = recovery_station_time(self.coalition.game.settings)
        time_to_landing = station_time.total_seconds()
        hdg = (self.coalition.game.conditions.weather.wind.at_0m.direction + 180) % 360
        recovery_ship = self.package.target.position.point_from_heading(
            hdg, time_to_landing * knots(20).meters_per_second
        )
        recovery_tanker = builder.recovery_tanker(recovery_ship)
        patrol_end = builder.race_track_end(recovery_tanker.position, altitude)
        patrol_end.only_for_player = True  # avoid generating the waypoints

        return PatrollingLayout(
            departure=builder.takeoff(self.flight.departure),
            nav_to=builder.nav_path(
                self.flight.departure.position, recovery_ship, altitude
            ),
            nav_from=builder.nav_path(
                recovery_ship, self.flight.arrival.position, altitude
            ),
            patrol_start=recovery_tanker,
            patrol_end=patrol_end,
            arrival=builder.land(self.flight.arrival),
            divert=builder.divert(self.flight.divert),
            bullseye=builder.bullseye(),
            custom_waypoints=list(),
        )

    def build(self, dump_debug_info: bool = False) -> RecoveryTankerFlightPlan:
        return RecoveryTankerFlightPlan(self.flight, self.layout())
