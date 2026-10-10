"""The one layer every transport calls; behaviour lives here so transports cannot drift.

Ported from juanjux/dcs-escalation `game/agent/service.py` (LGPL-3). Reads are always
open; writes need Developer tools > Outside AI plans red ticked. Every function that takes
``side`` refuses anything but red, here rather than in a router, so a second
transport cannot forget the rule: blue's ATO is the human's private side of the board.
Design note: docs/dev/design/retlab-llm-opfor-notes.md.
"""

from __future__ import annotations

import functools
import inspect
import re
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar, TYPE_CHECKING, cast

from game.agent import planner, schemas, views

if TYPE_CHECKING:
    from game import Game

OPFOR_SIDE = "red"

_F = TypeVar("_F", bound=Callable[..., Any])


class SideNotAllowedError(PermissionError):
    """Raised when the reader asks for a side other than red."""


def opfor_only(fn: _F) -> _F:
    signature = inspect.signature(fn)

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()
        side = str(bound.arguments.get("side", OPFOR_SIDE)).lower()
        if side != OPFOR_SIDE:
            raise SideNotAllowedError(
                f"this API reads {OPFOR_SIDE} only; {side!r} is the human player's "
                f"own side and is not readable through it"
            )
        return fn(*args, **kwargs)

    return cast(_F, wrapper)


def _require_game() -> Game:
    from game.server import GameContext

    return GameContext.require()


@opfor_only
def turn_context(side: str = OPFOR_SIDE) -> views.TurnContextView:
    return views.build_turn_context(_require_game(), side)


def settings() -> views.SettingsView:
    return views.build_settings(_require_game())


@opfor_only
def packages(side: str = OPFOR_SIDE) -> list[views.PackageView]:
    return views.build_packages(_require_game(), side)


@opfor_only
def waypoints(side: str = OPFOR_SIDE, flight_id: str = "") -> dict[str, Any]:
    """A red flight's route. Scoped to red: an id alone would reach blue's flights."""
    game = _require_game()
    coalition = views.coalition_for_side(game, side)
    for package in coalition.ato.packages:
        for flight in package.flights:
            if str(flight.id) == flight_id:
                return {
                    "flight_id": flight_id,
                    "waypoints": views.build_waypoints(game, flight),
                }
    raise KeyError(f"no {side} flight with id {flight_id!r}")


@opfor_only
def own_sites(side: str = OPFOR_SIDE) -> list[views.TargetView]:
    return views.build_own_ground_objects(_require_game(), side)


@opfor_only
def iads(side: str = OPFOR_SIDE) -> views.IadsView:
    return views.build_iads(_require_game(), side)


def prev_turns(n: int = 3) -> views.PrevTurnsView:
    return views.build_prev_turns(_require_game(), n)


@opfor_only
def map_image(side: str = OPFOR_SIDE, bbox: Optional[str] = None) -> bytes:
    from game.agent import mapimage

    game = _require_game()
    return mapimage.render(
        views.build_turn_context(game, side),
        bbox,
        own_sams=views.build_own_sams(game, side),
    )


def human_notes() -> dict[str, str]:
    """The campaign's Notes window: guidance the human left, read-only."""
    return {"notes": getattr(_require_game(), "notes", "") or ""}


def capabilities() -> dict[str, Any]:
    game = _require_game()
    return {
        "name": "RetLab OPFOR AI",
        "mode": "commander" if game.opfor_ai_enabled else "read and report",
        "side": OPFOR_SIDE,
        "docs": "GET /retribution-ai/start, then /retribution-ai/howtoplay",
        "reads": [
            "turn_context",
            "settings",
            "packages",
            "waypoints/{flight_id}",
            "iads",
            "ground/mine",
            "prev_turns",
            "map/image",
            "human_notes",
            "notes",
            "validate",
        ],
        "writes": (
            [
                "packages (POST create, DELETE all)",
                "packages/evaluate (plan and roll back)",
                "packages/{index} (DELETE)",
                "packages/{index}/tot",
                "stances",
                "buy/aircraft",
                "sell/aircraft",
                "buy/ground",
                "notes (PUT replace, POST merge, DELETE one key)",
            ]
            if game.opfor_ai_enabled
            else []
        ),
    }


# --- planning red (stage 2a) ---


class WritesOffError(PermissionError):
    """Raised when the AI writes while the Developer tools toggle is off."""


def _writable_game() -> Game:
    game = _require_game()
    if not game.opfor_ai_enabled:
        raise WritesOffError(
            "red is planned by the game's own planner: the human has not ticked "
            "Developer tools > Outside AI plans red, so this API is read-only"
        )
    return game


@opfor_only
def create_packages(
    side: str, specs: list[schemas.PackageSpec]
) -> list[schemas.CreateResult]:
    return planner.create_packages(_writable_game(), side, list(specs))


@opfor_only
def evaluate_package(side: str, spec: schemas.PackageSpec) -> schemas.EvaluateResult:
    return planner.evaluate_package(_writable_game(), side, spec)


@opfor_only
def validate_plan(side: str = OPFOR_SIDE) -> schemas.ValidateResult:
    return planner.validate_plan(_require_game(), side)


@opfor_only
def delete_package(side: str, index: int) -> schemas.OpResult:
    return planner.delete_package(_writable_game(), side, index)


@opfor_only
def clear_packages(side: str) -> schemas.OpResult:
    return planner.clear_packages(_writable_game(), side)


@opfor_only
def set_package_tot(
    side: str, index: int, tot_minutes: Optional[int]
) -> schemas.OpResult:
    return planner.set_package_tot(_writable_game(), side, index, tot_minutes)


@opfor_only
def set_stance(
    side: str, friendly_cp_id: str, enemy_cp_id: str, stance: str
) -> schemas.OpResult:
    return planner.set_stance(
        _writable_game(), side, friendly_cp_id, enemy_cp_id, stance
    )


@opfor_only
def buy_aircraft(side: str, squadron_id: str, quantity: int) -> schemas.OpResult:
    return planner.buy_aircraft(_writable_game(), side, squadron_id, quantity)


@opfor_only
def sell_aircraft(side: str, squadron_id: str, quantity: int) -> schemas.OpResult:
    return planner.sell_aircraft(_writable_game(), side, squadron_id, quantity)


@opfor_only
def buy_ground(
    side: str, cp_id: str, unit_name: str, quantity: int
) -> schemas.OpResult:
    return planner.buy_ground(_writable_game(), side, cp_id, unit_name, quantity)


def notes() -> dict[str, str]:
    """The AI's own notes, saved with the campaign."""
    return dict(_require_game().opfor_ai_notes)


def replace_notes(data: dict[str, str]) -> dict[str, str]:
    game = _writable_game()
    game.opfor_ai_notes = {str(k): str(v) for k, v in data.items()}
    return dict(game.opfor_ai_notes)


def merge_notes(data: dict[str, str]) -> dict[str, str]:
    game = _writable_game()
    game.opfor_ai_notes.update({str(k): str(v) for k, v in data.items()})
    return dict(game.opfor_ai_notes)


def delete_note(key: str) -> dict[str, str]:
    game = _writable_game()
    game.opfor_ai_notes.pop(key, None)
    return dict(game.opfor_ai_notes)


def run_fallback_if_needed(game: Game) -> bool:
    """At Take Off: if the AI cleared red's plan and planned nothing in its place, the
    scripted planner flies red's missions so the turn is never empty. True when it ran.
    """
    if not game.opfor_ai_enabled or game.red.ato.packages:
        return False
    game.red.plan_missions(game.conditions.start_time)
    return True


# --- connect URL and briefings ---


def _server_base() -> str:
    from game import persistency
    from game.server.settings import ServerSettings

    try:
        s = ServerSettings.get(persistency.server_port())
    except Exception:  # persistency not set up (tests)
        s = ServerSettings.get()
    host = str(s.server_bind_address)
    # "[::1]" reads as broken and trips clients that assume IPv4.
    if host in ("::1", "::", "0.0.0.0", "127.0.0.1", ""):
        host = "localhost"
    elif ":" in host:
        host = f"[{host}]"
    return f"http://{host}:{s.server_port}"


def connect_url() -> str:
    from game.server.security import ApiKeyManager

    return f"{_server_base()}/retribution-ai/start?token={ApiKeyManager.KEY}"


# Under resources/ so the PyInstaller build ships them; read relative to the cwd,
# as resources/whatsnew is.
_DOCS_DIR = Path("resources/agent")
_LEADING_COMMENT = re.compile(r"\A\s*<!--.*?-->\s*", re.DOTALL)


def _render_doc(name: str, subs: dict[str, str]) -> str:
    text = (_DOCS_DIR / name).read_text(encoding="utf-8")
    text = _LEADING_COMMENT.sub("", text, count=1)
    for key, value in subs.items():
        text = text.replace("{" + key + "}", value)
    return text


def start_doc(base_url: str) -> str:
    from game.server.security import ApiKeyManager

    return _render_doc(
        "start.md",
        {"BASE_URL": base_url.rstrip("/"), "TOKEN": ApiKeyManager.KEY},
    )


def howtoplay_doc() -> str:
    subs: dict[str, str] = {}
    try:
        game: Optional[Game] = _require_game()
    except Exception:
        game = None
    if game is not None:
        subs["RED_FACTION"] = game.red.faction.name
        subs["BLUE_FACTION"] = game.blue.faction.name
        subs["CAMPAIGN"] = game.campaign_name or "this campaign"
    return _render_doc("howtoplay.md", subs)
