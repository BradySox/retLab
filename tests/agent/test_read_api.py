"""The outside AI's read API: red only, token-gated, and the briefing matches the routes."""

import re
from datetime import datetime
from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi import HTTPException

from game.agent import service, views
from game.server.app import app
from game.server.retributionai.routes import router
from game.server.security import ApiKeyManager


@pytest.mark.parametrize(
    "call",
    [
        lambda: service.turn_context("blue"),
        lambda: service.packages("blue"),
        lambda: service.waypoints("blue", "anything"),
        lambda: service.iads("BLUE"),
        lambda: service.map_image("blue"),
    ],
)
def test_blue_is_refused_before_the_game_is_read(call: Any) -> None:
    # No GameContext is set: the guard must refuse before it is touched.
    with pytest.raises(service.SideNotAllowedError):
        call()


def test_token_by_header_or_query() -> None:
    key = ApiKeyManager.KEY
    ApiKeyManager.verify(key, None)
    ApiKeyManager.verify(None, key)
    for header, query in ((None, None), ("wrong", None), (None, "wrong")):
        with pytest.raises(HTTPException) as raised:
            ApiKeyManager.verify(header, query)
        assert raised.value.status_code == 403


def test_every_ai_route_needs_the_token_and_the_map_routes_do_not() -> None:
    assert [d.dependency for d in router.dependencies] == [ApiKeyManager.verify]
    ai_paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/retribution-ai/turn_context" in ai_paths
    # The map server's own routes were open before this and stay open.
    tgos = next(r for r in app.routes if getattr(r, "path", "") == "/tgos/")
    assert not getattr(tgos, "dependencies", [])


def test_the_briefing_names_only_routes_that_exist() -> None:
    text = service.start_doc("http://localhost:16880") + service.howtoplay_doc()
    named = set(re.findall(r"/retribution-ai/([a-z_/]+)", text))
    paths = {r.path.removeprefix("/retribution-ai/") for r in router.routes}  # type: ignore[attr-defined]
    for name in named:
        assert any(
            p == name or p.startswith(name.rstrip("/") + "/{") for p in paths
        ), name
    assert named >= {"turn_context", "packages", "prev_turns", "iads", "howtoplay"}


def test_connect_url_carries_the_token() -> None:
    url = service.connect_url()
    assert url.startswith("http://localhost:")
    assert url.endswith(f"/retribution-ai/start?token={ApiKeyManager.KEY}")


def _target(tid: str, kind: str, threat: int | None) -> views.TargetView:
    return views.TargetView(
        id=tid, name=tid, kind=kind, suggested_task="DEAD", pos=[0, 0], threat_nm=threat
    )


def test_threats_are_every_umbrella_ranked_by_reach() -> None:
    targets = [_target(f"s{i}", "sam", 24) for i in range(15)]
    targets += [
        _target("big", "sam", 80),
        _target("ship", "ship", 60),
        _target("building", "building", 5),
        _target("ewr", "sam", None),
    ]
    threats = views.build_threats(targets)
    assert [t.id for t in threats[:2]] == ["big", "ship"]
    assert len(threats) == 17


def _squadron(owned: int, untasked: int, pilots: int, reserve: int = 0) -> Any:
    location = SimpleNamespace(captured="red", runway_is_operational=lambda: True)
    return SimpleNamespace(
        owned_aircraft=owned,
        untasked_aircraft=untasked,
        number_of_available_pilots=pilots,
        pilot_limits_enabled=True,
        intercept_reserve=reserve,
        location=location,
    )


def test_flyable_is_capped_by_pilots_and_qra_is_named() -> None:
    assert views._squadron_flyable(_squadron(12, 10, 4), grounded=False) == 4
    assert views._squadron_flyable(_squadron(12, 10, 4), grounded=True) == 0
    held = _squadron(4, 0, 4, reserve=4)
    assert views._unflyable_reason(held, grounded=False) == (
        "4 held on QRA alert, the rest tasked"
    )
    assert views._unflyable_reason(_squadron(4, 0, 4), grounded=False) == (
        "all 4 already tasked"
    )


def _turn(blue: int, red: int) -> Any:
    side = lambda n: SimpleNamespace(aircraft_count=n, vehicles_count=0)
    return SimpleNamespace(allied_units=side(blue), enemy_units=side(red))


def test_prev_turns_leaves_out_the_turn_being_planned() -> None:
    game = SimpleNamespace(
        turn=2,
        game_stats=SimpleNamespace(
            data_per_turn=[_turn(10, 20), _turn(9, 18), _turn(9, 17)]
        ),
        last_sitrep=None,
        informations=[SimpleNamespace(turn=1, title="Lost", text="a jet")],
    )
    result = views.build_prev_turns(cast(Any, game), n=5)
    assert [t.turn for t in result.trend] == [0, 1]
    assert result.trend[-1].red.aircraft == 18
    assert result.events == ["Lost: a jet"]


@pytest.mark.parametrize(
    "line, expected",
    [
        (
            "Enemy reinforcements: T-55A x 2 at Alta",
            "Red reinforcements: T-55A x 2 at Alta",
        ),
        (
            "Ally reinforcements: M113 x 9 at Bardufoss",
            "Blue reinforcements: M113 x 9 at Bardufoss",
        ),
        ("We took control of Alta.", "Blue took control of Alta."),
        ("The enemy took control of Evenes.", "Red took control of Evenes."),
        (
            "Our ground forces from A reached a stalemate with enemy forces from B",
            "Blue's ground forces from A reached a stalemate with red forces from B",
        ),
        ("OPFOR has begun repairing the runway at Banak", None),
        # Whichever side owns the base: not blue's word.
        ("Alta is not connected to any friendly points.", None),
    ],
)
def test_the_campaign_log_names_the_sides(line: str, expected: str | None) -> None:
    if expected is None:
        expected = line.replace("OPFOR", "Red")
    assert views.name_the_sides(line) == expected


def _flight_with_loadout(restrict: bool) -> Any:
    planned = SimpleNamespace(
        name="Anti-ship", pylons={2: SimpleNamespace(name="Kh-31A")}
    )
    dated = SimpleNamespace(
        name="Anti-ship", pylons={2: SimpleNamespace(name="Kh-29L"), 5: None}
    )
    planned.degrade_for_date = lambda *args: dated
    game = SimpleNamespace(
        settings=SimpleNamespace(restrict_weapons_by_date=restrict), date=None
    )
    return SimpleNamespace(
        iter_members=lambda: iter([SimpleNamespace(loadout=planned)]),
        coalition=SimpleNamespace(game=game),
        unit_type=None,
        squadron=SimpleNamespace(coalition=SimpleNamespace(faction=None)),
        package=SimpleNamespace(target=None),
    )


def test_a_loadout_is_the_one_the_mission_is_built_with() -> None:
    # The date rule runs at generation, so the planned fit lists weapons never loaded.
    assert views._flight_loadout(_flight_with_loadout(True)) == (
        "Anti-ship",
        {2: "Kh-29L"},
    )
    assert views._flight_loadout(_flight_with_loadout(False)) == (
        "Anti-ship",
        {2: "Kh-31A"},
    )
