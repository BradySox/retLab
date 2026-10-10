"""The outside AI's write path: gated on the toggle, red only, and the engine hands red's
turn over to it."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Iterator, cast
from unittest.mock import MagicMock, patch

import pytest

from game import Game
from game.agent import planner, schemas, service
from game.ato.flighttype import FlightType
from game.coalition import Coalition
from game.server import GameContext
from game.settings import Settings
from game.settings.layout import FIELD_LAYOUT
from game.theater.player import Player


@pytest.fixture
def live_game() -> Iterator[Any]:
    game = SimpleNamespace(
        settings=SimpleNamespace(outside_ai_plans_red=False), opfor_ai_notes={}
    )
    previous = getattr(GameContext, "_game_model", None)
    GameContext.set_model(cast(Any, SimpleNamespace(game=game)))
    yield game
    if previous is not None:
        GameContext.set_model(previous)


def test_writes_are_refused_until_the_toggle_is_on(live_game: Any) -> None:
    with pytest.raises(service.WritesOffError):
        service.clear_packages("red")
    with pytest.raises(service.WritesOffError):
        service.merge_notes({"plan": "x"})
    assert service.notes() == {}
    live_game.settings.outside_ai_plans_red = True
    assert service.merge_notes({"plan": "hold"}) == {"plan": "hold"}
    assert service.replace_notes({"a": "1"}) == {"a": "1"}
    assert service.delete_note("a") == {}


def test_blue_writes_are_refused_even_with_the_toggle_on(live_game: Any) -> None:
    live_game.settings.outside_ai_plans_red = True
    with pytest.raises(service.SideNotAllowedError):
        service.clear_packages("blue")
    with pytest.raises(service.SideNotAllowedError):
        service.buy_aircraft("blue", "id", 1)


@pytest.mark.parametrize(
    "name, expected",
    [
        ("STRIKE", FlightType.STRIKE),
        ("cap", FlightType.BARCAP),
        ("SEAD escort", FlightType.SEAD_ESCORT),
        ("Anti-ship", FlightType.ANTISHIP),
        ("oca_runway", FlightType.OCA_RUNWAY),
    ],
)
def test_task_names_a_model_reaches_for(name: str, expected: FlightType) -> None:
    assert planner._flight_type(name) is expected


def test_unknown_task_and_escort_are_named() -> None:
    with pytest.raises(ValueError, match="unknown task"):
        planner._flight_type("bombing run")
    with pytest.raises(ValueError, match="unknown escort"):
        planner._escort_type("wingman")


def _coalition(player: Player, ai_on: bool) -> Any:
    fake = MagicMock()
    fake.player = player
    fake.game.settings.outside_ai_plans_red = ai_on
    return fake


@pytest.mark.parametrize(
    "player, ai_on",
    [
        (Player.RED, False),
        (Player.RED, True),
        (Player.BLUE, True),
    ],
)
def test_the_scripted_planner_plans_and_buys_at_turn_start_with_the_ai_on(
    player: Player, ai_on: bool
) -> None:
    # A turn start or a mid-turn re-plan clears the ATO and refunds the orders, so
    # standing the planner down for the AI left red with no plan and no purchases.
    coalition = _coalition(player, ai_on)
    Coalition.initialize_turn(coalition, is_turn_0=False, events=MagicMock())
    coalition.plan_missions.assert_called_once()
    coalition.plan_procurement.assert_called_once()


def test_turn_0_buys_and_plans_no_missions_with_the_ai_on() -> None:
    coalition = _coalition(Player.RED, ai_on=True)
    Coalition.initialize_turn(coalition, is_turn_0=True, events=MagicMock())
    coalition.plan_missions.assert_not_called()
    coalition.plan_procurement.assert_called_once()


def test_take_off_fallback_runs_only_when_the_ai_planned_nothing() -> None:
    game = MagicMock()
    game.settings.outside_ai_plans_red = True
    game.red.ato.packages = []
    assert service.run_fallback_if_needed(game)
    game.red.plan_missions.assert_called_once()

    game.red.plan_missions.reset_mock()
    game.red.ato.packages = [object()]
    assert not service.run_fallback_if_needed(game)
    game.settings.outside_ai_plans_red = False
    game.red.ato.packages = []
    assert not service.run_fallback_if_needed(game)
    game.red.plan_missions.assert_not_called()


def test_a_stance_is_only_set_on_reds_own_front(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blue_cp = SimpleNamespace(
        id="b", name="Blue base", captured=Player.BLUE, stances={}
    )
    red_cp = SimpleNamespace(id="r", name="Red base", captured=Player.RED, stances={})
    by_id = {"b": blue_cp, "r": red_cp}
    game: Any = SimpleNamespace()
    monkeypatch.setattr(planner, "_resolve_cp", lambda g, cp_id: by_id[cp_id])
    refused = planner.set_stance(game, "red", "b", "r", "push")
    assert not refused.ok and "not yours" in (refused.error or "")
    no_front = planner.set_stance(game, "red", "r", "b", "push")
    assert not no_front.ok and "no front" in (no_front.error or "")
    red_cp.stances["b"] = None
    done = planner.set_stance(game, "red", "r", "b", "push")
    assert done.ok and red_cp.stances["b"].name == "AGGRESSIVE"


def test_package_spec_defaults() -> None:
    spec = schemas.PackageSpec(target_id="x", flights=[schemas.FlightSpec(task="CAS")])
    assert spec.tot_minutes is None and not spec.ignore_range
    assert spec.flights[0].count == 2


@pytest.mark.parametrize("ticked", [True, False])
def test_a_save_from_the_developer_tools_toggle_keeps_its_choice(ticked: bool) -> None:
    # Until 2026-10-10 the switch was Game.opfor_ai_enabled, not a setting.
    game = Game.__new__(Game)
    state: dict[str, Any] = {
        "opfor_ai_enabled": ticked,
        "settings": Settings(),
        # Present so __setstate__ does not walk a theater this bare instance lacks.
        "laser_code_registry": object(),
    }
    with patch.object(Game, "on_load"):
        game.__setstate__(state)
    assert game.settings.outside_ai_plans_red is ticked
    assert not hasattr(game, "opfor_ai_enabled")


def test_the_switch_is_a_setting_the_new_game_wizard_shows() -> None:
    assert FIELD_LAYOUT["outside_ai_plans_red"] == (
        "Campaign Management",
        "HQ automation",
    )
    assert Settings().outside_ai_plans_red is False


def _package(need_min: float, support: bool = False) -> Any:
    plan = SimpleNamespace(
        minimum_duration_from_start_to_tot=lambda: timedelta(minutes=need_min),
        tot_offset=timedelta(),
    )
    flight = SimpleNamespace(
        flight_plan=plan, departure=SimpleNamespace(name="Severomorsk-1")
    )
    return SimpleNamespace(
        flights=[flight],
        auto_asap=support,
        primary_task=FlightType.REFUELING if support else FlightType.DEAD,
    )


def test_a_start_the_early_mission_start_covers_is_not_a_shortfall() -> None:
    # §104: a later package lengthens the runway queue, so the scripted planner's own
    # package can need to start a minute before the turn clock.
    now = datetime(1985, 9, 11, 1, 0)
    tot = now + timedelta(minutes=55, seconds=51)
    package = _package(57)
    assert planner.tot_shortfall(package, now, tot) is None
    assert planner.early_start_minutes(package, now, tot) == 1
    assert planner.early_start_minutes(_package(55), now, tot) is None


def test_a_start_past_the_early_start_cap_is_a_shortfall() -> None:
    now = datetime(1985, 9, 11, 1, 0)
    tot = now + timedelta(minutes=55)
    assert planner.tot_shortfall(_package(90), now, tot) == (60, "Severomorsk-1")
    # ASAP support launches with the mission, early or not, so it gets no lead.
    assert planner.tot_shortfall(_package(57, support=True), now, tot) == (
        57,
        "Severomorsk-1",
    )
