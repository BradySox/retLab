"""A support track slides along its own length, out of neutral airspace.

Read off a Kola turn 2026-10-10: red's IL-78 track ran 11 NM into neutral
Finland, and the A-50's ended 4 NM from the border.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
import yaml
from dcs import Point
from dcs.mapping import LatLng
from dcs.terrain import Caucasus, Kola

from game.ato.flightplans.patrolling import (
    NEUTRAL_BORDER_MARGIN,
    slide_clear_of_neutral_airspace,
)
from game.utils import nautical_miles

TERRAIN = Caucasus()
NM = nautical_miles(1).meters


def _p(x_nm: float, y_nm: float) -> Point:
    return Point(x_nm * NM, y_nm * NM, TERRAIN)


def _square(x0: float, y0: float, x1: float, y1: float) -> list[tuple[float, float]]:
    return [
        (x0 * NM, y0 * NM),
        (x1 * NM, y0 * NM),
        (x1 * NM, y1 * NM),
        (x0 * NM, y1 * NM),
    ]


def _coalition(
    *borders: list[tuple[float, float]], enforced: bool = True, setting: bool = True
) -> Any:
    zones = [
        SimpleNamespace(border=border, enforces_against=lambda *_: enforced)
        for border in borders
    ]
    return SimpleNamespace(
        player=SimpleNamespace(is_blue=False),
        game=SimpleNamespace(
            settings=SimpleNamespace(neutral_border_defense=setting),
            theater=SimpleNamespace(neutral_border_zones=zones),
        ),
    )


def _threats(threatened: Any = lambda _: False) -> Any:
    return SimpleNamespace(threatened=threatened)


# A track running north (+x) from (0, 0) to (40, 0); the neutral country covers
# its southern 10 NM.
START, END = _p(40, 0), _p(0, 0)
SOUTH = _square(-200, -50, 10, 50)


def test_slides_north_by_the_overlap_plus_the_margin() -> None:
    start, end = slide_clear_of_neutral_airspace(
        START, END, _coalition(SOUTH), _threats()
    )
    moved = (end.x - END.x) / NM
    margin = NEUTRAL_BORDER_MARGIN.nautical_miles
    assert moved == pytest.approx(10 + margin, abs=1.01)
    assert (start.x - START.x) / NM == pytest.approx(moved)
    assert start.y == pytest.approx(START.y, abs=1) and end.y == pytest.approx(0, abs=1)


def test_takes_the_shorter_way_out() -> None:
    # The country covers the northern 10 NM instead: the way out is south.
    north = _square(30, -50, 200, 50)
    start, end = slide_clear_of_neutral_airspace(
        START, END, _coalition(north), _threats()
    )
    assert start.x < START.x


def test_a_clear_track_does_not_move() -> None:
    far = _square(-300, -50, -100, 50)
    assert slide_clear_of_neutral_airspace(START, END, _coalition(far), _threats()) == (
        START,
        END,
    )


def test_a_country_that_lets_this_side_through_is_ignored() -> None:
    coalition = _coalition(SOUTH, enforced=False)
    assert slide_clear_of_neutral_airspace(START, END, coalition, _threats()) == (
        START,
        END,
    )


def test_off_with_the_border_setting() -> None:
    coalition = _coalition(SOUTH, setting=False)
    assert slide_clear_of_neutral_airspace(START, END, coalition, _threats()) == (
        START,
        END,
    )


def test_never_slides_into_a_threat_zone() -> None:
    # North is the short way out but is threatened, so the track goes south.
    north_is_hot = _threats(lambda point: point.x > 45 * NM)
    middle = _square(5, -50, 12, 50)
    start, end = slide_clear_of_neutral_airspace(
        START, END, _coalition(middle), north_is_hot
    )
    assert start.x < START.x


def test_stays_put_when_nothing_in_reach_is_clear() -> None:
    everywhere = _square(-500, -500, 500, 500)
    assert slide_clear_of_neutral_airspace(
        START, END, _coalition(everywhere), _threats()
    ) == (START, END)


def test_a_coalition_with_no_theater_is_left_alone() -> None:
    bare = SimpleNamespace(game=SimpleNamespace(settings=SimpleNamespace()))
    assert slide_clear_of_neutral_airspace(START, END, bare, _threats()) == (
        START,
        END,
    )


def test_the_kola_tanker_track_leaves_finland() -> None:
    """The flown case, against the shipped border file."""
    terrain = Kola()
    with open("resources/borders/kola.yaml", encoding="utf-8") as borders:
        zones = yaml.safe_load(borders)["zones"]
    finland = [zone["border"] for zone in zones if zone["country"] == "Finland"]
    start = Point.from_latlng(LatLng(69.2232, 24.3054), terrain)
    end = Point.from_latlng(LatLng(68.56536, 24.05001), terrain)

    new_start, new_end = slide_clear_of_neutral_airspace(
        start, end, _coalition(*finland), _threats()
    )

    moved = new_start.distance_to_point(start) / NM
    assert 15 < moved < 30
    assert new_start.x > start.x  # north
    assert new_start.distance_to_point(new_end) == pytest.approx(
        start.distance_to_point(end), rel=0.001
    )
