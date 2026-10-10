"""An air-started AI AWACS or theater tanker spawns on its track.

The "Support aircraft (AWACS/tankers) start in the air" setting says on station
from mission start. Spawned over its own field, a Kola A-50 flew 190 NM and was
on station 31 minutes in (2026-10-10).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from dcs import Point
from dcs.terrain import Caucasus

from game.ato.flightplans.aewc import AewcFlightPlan
from game.ato.flightplans.patrolling import (
    PatrollingLayout,
    support_spawns_on_station,
)
from game.ato.flightplans.theaterrefueling import TheaterRefuelingFlightPlan
from game.ato.flighttype import FlightType
from game.ato.flightwaypoint import FlightWaypoint
from game.ato.flightwaypointtype import FlightWaypointType
from game.ato.starttype import StartType
from game.missiongenerator.aircraft.flightgroupspawner import (
    ON_STATION_LEAD_IN,
    FlightGroupSpawner,
)
from game.missiongenerator.aircraft.waypoints.waypointgenerator import (
    WaypointGenerator,
)
from game.utils import feet, knots, nautical_miles

TERRAIN = Caucasus()
ALT = feet(25000)
TOT = datetime(1985, 9, 10, 16, 31)


def _wp(name: str, kind: FlightWaypointType, x_nm: float, y_nm: float) -> Any:
    position = Point(nautical_miles(x_nm).meters, nautical_miles(y_nm).meters, TERRAIN)
    return FlightWaypoint(name, kind, position, ALT)


def _flight(
    *,
    start_type: StartType = StartType.IN_FLIGHT,
    clients: int = 0,
    setting: bool = True,
    flight_type: FlightType = FlightType.AEWC,
) -> Any:
    settings = SimpleNamespace(support_air_start=setting)
    return SimpleNamespace(
        start_type=start_type,
        client_count=clients,
        flight_type=flight_type,
        manually_timed=False,
        coalition=SimpleNamespace(game=SimpleNamespace(settings=settings)),
        package=SimpleNamespace(time_over_target=TOT),
    )


def _plan(cls: Any, flight: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    """A track 190 NM east of the field, with one nav point on the way out."""
    monkeypatch.setattr(cls, "speed_between_waypoints", lambda *_: knots(360))
    plan = cls.__new__(cls)
    plan.flight = flight
    plan.tot_offset = timedelta()
    plan.layout = PatrollingLayout(
        departure=_wp("takeoff", FlightWaypointType.TAKEOFF, 0, 0),
        nav_to=[_wp("nav", FlightWaypointType.NAV, 0, 100)],
        nav_from=[],
        patrol_start=_wp("start", FlightWaypointType.PATROL_TRACK, 30, 190),
        patrol_end=_wp("end", FlightWaypointType.PATROL, -30, 190),
        arrival=_wp("land", FlightWaypointType.LANDING_POINT, 0, 0),
        divert=None,
        bullseye=_wp("bullseye", FlightWaypointType.BULLSEYE, 0, 0),
        custom_waypoints=[],
    )
    return plan


def _spawner(plan: Any, *, in_flight: bool = False, passed_start: bool = False) -> Any:
    state = SimpleNamespace()
    if in_flight:
        state.has_passed_waypoint = lambda _: passed_start
    return SimpleNamespace(flight=SimpleNamespace(flight_plan=plan, state=state))


@pytest.mark.parametrize(
    "start_type,clients,setting,expected",
    [
        (StartType.IN_FLIGHT, 0, True, True),
        (StartType.IN_FLIGHT, 0, False, False),
        (StartType.IN_FLIGHT, 1, True, False),
        (StartType.WARM, 0, True, False),
        (StartType.COLD, 0, True, False),
    ],
)
def test_only_an_ai_air_start_under_the_setting(
    start_type: StartType, clients: int, setting: bool, expected: bool
) -> None:
    flight = _flight(start_type=start_type, clients=clients, setting=setting)
    assert support_spawns_on_station(flight) is expected


@pytest.mark.parametrize("cls", [AewcFlightPlan, TheaterRefuelingFlightPlan])
def test_the_way_out_costs_no_time(cls: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    kind = FlightType.AEWC if cls is AewcFlightPlan else FlightType.REFUELING
    plan = _plan(cls, _flight(flight_type=kind), monkeypatch)
    assert plan.starts_on_station
    assert plan._travel_time_to_waypoint(plan.layout.patrol_start) == timedelta()
    assert plan.takeoff_time() == TOT


@pytest.mark.parametrize("cls", [AewcFlightPlan, TheaterRefuelingFlightPlan])
def test_a_ground_start_still_flies_out(
    cls: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    kind = FlightType.AEWC if cls is AewcFlightPlan else FlightType.REFUELING
    flight = _flight(start_type=StartType.WARM, flight_type=kind)
    plan = _plan(cls, flight, monkeypatch)
    assert not plan.starts_on_station
    assert plan._travel_time_to_waypoint(plan.layout.patrol_start) > timedelta(
        minutes=30
    )


def test_the_way_home_is_still_flown(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _plan(AewcFlightPlan, _flight(), monkeypatch)
    home = plan.travel_time_between_waypoints(
        plan.layout.patrol_end, plan.layout.arrival
    )
    assert home > timedelta(minutes=30)


def test_the_way_out_burns_no_fuel(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _plan(TheaterRefuelingFlightPlan, _flight(), monkeypatch)
    layout = plan.layout
    for a, b in (
        (layout.departure, layout.nav_to[0]),
        (layout.nav_to[0], layout.patrol_start),
    ):
        assert plan.fuel_burn_distance_between_points(a, b).meters == 0


def test_a_jammer_on_the_awacs_plan_flies_out(monkeypatch: pytest.MonkeyPatch) -> None:
    flight = _flight(flight_type=FlightType.JAMMING)
    plan = _plan(AewcFlightPlan, flight, monkeypatch)
    assert not plan.starts_on_station


def test_spawns_short_of_the_track_on_its_own_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan(AewcFlightPlan, _flight(), monkeypatch)
    spawn = FlightGroupSpawner._on_station_spawn(_spawner(plan))
    assert spawn is not None
    position, altitude, alt_type = spawn
    start, end = plan.layout.patrol_start.position, plan.layout.patrol_end.position
    lead_in = ON_STATION_LEAD_IN.meters
    assert position.distance_to_point(start) == pytest.approx(lead_in, rel=0.01)
    track = start.distance_to_point(end)
    assert position.distance_to_point(end) == pytest.approx(track + lead_in, rel=0.01)
    assert altitude == ALT
    assert alt_type == plan.layout.patrol_start.alt_type


def test_a_flight_that_flies_out_spawns_over_its_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    flight = _flight(start_type=StartType.WARM)
    plan = _plan(AewcFlightPlan, flight, monkeypatch)
    assert FlightGroupSpawner._on_station_spawn(_spawner(plan)) is None


def test_the_sim_still_on_the_way_out_spawns_on_the_track(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Generation at mission start finds the flight airborne on its first leg.
    plan = _plan(AewcFlightPlan, _flight(), monkeypatch)
    spawner = _spawner(plan, in_flight=True, passed_start=False)
    assert FlightGroupSpawner._on_station_spawn(spawner) is not None


def test_a_flight_the_sim_has_on_its_track_spawns_where_it_is(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan(AewcFlightPlan, _flight(), monkeypatch)
    spawner = _spawner(plan, in_flight=True, passed_start=True)
    assert FlightGroupSpawner._on_station_spawn(spawner) is None


def test_the_route_out_is_left_off_the_mission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan(AewcFlightPlan, _flight(), monkeypatch)
    generator = SimpleNamespace(flight=SimpleNamespace(flight_plan=plan))
    skipped = WaypointGenerator.points_flown_before_spawn(
        generator  # type: ignore[arg-type]
    )
    assert skipped == plan.layout.nav_to


def test_a_flight_that_flies_out_keeps_its_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan(AewcFlightPlan, _flight(start_type=StartType.WARM), monkeypatch)
    generator = SimpleNamespace(flight=SimpleNamespace(flight_plan=plan))
    assert not WaypointGenerator.points_flown_before_spawn(
        generator  # type: ignore[arg-type]
    )
