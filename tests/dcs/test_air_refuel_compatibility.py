"""Tests for AircraftType air-to-air refueling compatibility (can_refuel_from).

The compatibility check is intentionally permissive: an untagged receiver or an
untagged tanker is always compatible so the boom/probe restriction is opt-in and
never regresses campaigns whose aircraft data hasn't been classified yet.
"""

from types import SimpleNamespace

import pytest

from game import persistency
from game.dcs.aircrafttype import NO_AIR_REFUEL, AircraftType, AirRefuelType


def _receiver(
    air_refuel_type: object = None, helicopter: bool = False, cannot: bool = False
) -> SimpleNamespace:
    return SimpleNamespace(
        air_refuel_type=air_refuel_type, helicopter=helicopter, cannot_air_refuel=cannot
    )


def _tanker(
    provides: frozenset[AirRefuelType] = frozenset(), helicopters: bool = False
) -> SimpleNamespace:
    return SimpleNamespace(
        tanker_refuel_types=provides, tanker_refuels_helicopters=helicopters
    )


def _can_refuel(receiver: object, tanker: object) -> bool:
    # Call the unbound method so we can pass lightweight duck-typed stand-ins instead
    # of building a fully-populated frozen AircraftType.
    return AircraftType.can_refuel_from(receiver, tanker)  # type: ignore[arg-type]


def test_untagged_receiver_is_compatible_with_anything() -> None:
    assert _can_refuel(_receiver(None), _tanker(frozenset({AirRefuelType.BOOM})))


def test_tagged_receiver_is_compatible_with_untagged_tanker() -> None:
    # A tanker that advertises no methods is treated permissively (legacy behavior).
    assert _can_refuel(_receiver(AirRefuelType.BOOM), _tanker(frozenset()))


def test_boom_receiver_matches_boom_tanker_only() -> None:
    boom = _receiver(AirRefuelType.BOOM)
    assert _can_refuel(boom, _tanker(frozenset({AirRefuelType.BOOM})))
    assert not _can_refuel(boom, _tanker(frozenset({AirRefuelType.PROBE})))


def test_probe_receiver_matches_probe_tanker_only() -> None:
    probe = _receiver(AirRefuelType.PROBE)
    assert _can_refuel(probe, _tanker(frozenset({AirRefuelType.PROBE})))
    assert not _can_refuel(probe, _tanker(frozenset({AirRefuelType.BOOM})))


def test_multi_method_tanker_serves_both() -> None:
    both = _tanker(frozenset({AirRefuelType.BOOM, AirRefuelType.PROBE}))
    assert _can_refuel(_receiver(AirRefuelType.BOOM), both)
    assert _can_refuel(_receiver(AirRefuelType.PROBE), both)


def test_helicopter_needs_a_slow_capable_tanker() -> None:
    helo = _receiver(AirRefuelType.PROBE, helicopter=True)
    # A fast drogue tanker (e.g. KC-135 MPRS) can't service a helo...
    assert not _can_refuel(helo, _tanker(frozenset({AirRefuelType.PROBE})))
    # ...but a slow-capable one (e.g. KC-130) can.
    assert _can_refuel(
        helo, _tanker(frozenset({AirRefuelType.PROBE}), helicopters=True)
    )


def test_a_receiver_that_cannot_refuel_takes_no_tanker() -> None:
    # Unset used to mean "takes any tanker": a Su-25 was routed to an IL-78 track.
    none = _receiver(cannot=True)
    assert not _can_refuel(none, _tanker(frozenset()))
    assert not _can_refuel(none, _tanker(frozenset({AirRefuelType.PROBE})))
    assert not _can_refuel(
        none, _tanker(frozenset({AirRefuelType.BOOM, AirRefuelType.PROBE}))
    )


def test_the_none_tag_is_not_a_refuel_method() -> None:
    # A method would make the planner look for a tanker that dispenses it.
    assert AirRefuelType.from_data(NO_AIR_REFUEL) is None
    assert AirRefuelType.from_data(None) is None
    assert AirRefuelType.from_data("probe") is AirRefuelType.PROBE


@pytest.fixture(scope="module")
def unit_data(tmp_path_factory: pytest.TempPathFactory) -> None:
    persistency.setup(str(tmp_path_factory.mktemp("saved_games")), False, 0)


@pytest.mark.parametrize(
    "name",
    [
        "Su-25 Frogfoot",
        "Su-17M4 Fitter-K",
        "MiG-23MLD Flogger-K",
        "MiG-25PD Foxbat-E",
        "Su-27 Flanker-B",
        "Tu-22M3 Backfire-C",
    ],
)
def test_airframes_dcs_gives_no_probe_take_no_tanker(
    unit_data: None, name: str
) -> None:
    # DCS's own unit data carries no "Refuelable" attribute for these.
    aircraft = AircraftType.named(name)
    assert aircraft.cannot_air_refuel
    assert aircraft.air_refuel_type is None
    assert not aircraft.can_refuel_from(AircraftType.named("IL-78M"))
    assert not aircraft.can_refuel_from(AircraftType.named("KC-135 Stratotanker"))


@pytest.mark.parametrize("name", ["Su-24M Fencer-D", "MiG-31 Foxhound"])
def test_probe_airframes_still_take_the_il78(unit_data: None, name: str) -> None:
    aircraft = AircraftType.named(name)
    assert not aircraft.cannot_air_refuel
    assert aircraft.can_refuel_from(AircraftType.named("IL-78M"))
