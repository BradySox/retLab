"""BARCAP stations fill nearest the enemy first, not in campaign-file order."""

from __future__ import annotations

from dataclasses import dataclass

from game.commander.theaterstate import barcap_order
from game.utils import nautical_miles


@dataclass(eq=False)
class _Base:
    name: str
    x_nm: float
    is_fleet: bool = False

    def distance_to(self, other: _Base) -> float:
        return nautical_miles(abs(self.x_nm - other.x_nm)).meters


def _names(bases: list[_Base], enemies: list[_Base]) -> list[str]:
    return [b.name for b in barcap_order(bases, enemies)]  # type: ignore[arg-type]


def test_front_fields_come_before_rear_fields() -> None:
    # Crossing the Rubicon's file order: the rear fields are listed first.
    templin = _Base("Templin", 214)
    peenemunde = _Base("Peenemunde", 271)
    haina = _Base("Haina", 47)
    fulda = _Base("Fulda", 4)
    frankfurt = _Base("Frankfurt", 0)

    order = _names([templin, peenemunde, haina, fulda], [frankfurt])

    assert order == ["Fulda", "Haina", "Templin", "Peenemunde"]


def test_distance_is_to_the_nearest_enemy_base() -> None:
    west = _Base("West", 0)
    east = _Base("East", 300)
    near_east = _Base("Near east", 280)
    middle = _Base("Middle", 150)

    assert _names([middle, near_east], [west, east]) == ["Near east", "Middle"]


def test_carriers_come_first_and_keep_their_order() -> None:
    field = _Base("Field", 10)
    cvn = _Base("CVN", 400, is_fleet=True)
    lha = _Base("LHA", 500, is_fleet=True)

    assert _names([field, cvn, lha], [_Base("Enemy", 0)]) == ["CVN", "LHA", "Field"]


def test_a_base_yielded_twice_is_listed_once() -> None:
    field = _Base("Field", 10)

    assert _names([field, field], [_Base("Enemy", 0)]) == ["Field"]


def test_no_enemy_bases_keeps_the_given_order() -> None:
    a, b = _Base("A", 50), _Base("B", 5)

    assert _names([a, b], []) == ["A", "B"]
