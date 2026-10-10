"""What the outside AI reads: red's picture of the turn, as compact pydantic models.

Ported from juanjux/dcs-escalation `game/agent/views.py` (LGPL-3, as this tree), cut
to what RetLab's engine has: no pilot morale, High Command, rebuild timers or derived
IADS state. Pure functions over a `Game`, so they test without the server or Qt.

Payloads go to the model every turn, so they are frugal: coordinates are bare
`[lat, lng]`, TOT is `HH:MM`, and a field that would be zero or empty is None so the
transport drops it. The briefing (`resources/agent/howtoplay.md`) says once that absent means 0.
Red sees blue as the scripted red planner does (ground truth), never blue's ATO.
Design note: docs/dev/design/retlab-llm-opfor-notes.md.
"""

from __future__ import annotations

import math
import re
from datetime import timedelta
from typing import Any, Optional, TYPE_CHECKING

from dcs.mapping import Point as DcsPoint
from dcs.weather import Weather as PydcsWeather, Wind
from pydantic import BaseModel

from game.income import Income
from game.theater.player import Player
from game.utils import meters, mps

if TYPE_CHECKING:
    from game import Game
    from game.ato import Flight, Package
    from game.coalition import Coalition
    from game.squadrons.squadron import Squadron
    from game.theater import ControlPoint, TheaterGroundObject
    from game.weather.clouds import Clouds


_SIDE_TO_PLAYER = {"red": Player.RED, "blue": Player.BLUE}

# check_win_loss() is blue-centric; the reader is red.
_CAMPAIGN_STATE_FROM_RED = {
    "CONTINUE": "ongoing",
    "WIN": "red_losing",
    "LOSS": "red_winning",
}


def player_for_side(side: str) -> Player:
    try:
        return _SIDE_TO_PLAYER[side.lower()]
    except KeyError:
        raise ValueError(f"side must be 'red' or 'blue', got {side!r}")


def coalition_for_side(game: Game, side: str) -> Coalition:
    return game.coalition_for(player_for_side(side))


def _r(value: float, ndigits: int = 5) -> float:
    return round(float(value), ndigits)


def _latlng(game: Game, x: float, y: float) -> list[float]:
    ll = DcsPoint(x, y, game.theater.terrain).latlng()
    return [_r(ll.lat), _r(ll.lng)]


def _enum_str(value: object) -> Optional[str]:
    if value is None:
        return None
    member_value = getattr(value, "value", None)
    if member_value is not None:
        return str(member_value)
    return getattr(value, "name", None) or str(value)


class WeatherView(BaseModel):
    clouds: str  # "clear", a coverage code ("SCT"), or a preset's name
    base_ft: Optional[int] = None
    precip: Optional[str] = None
    vis_nm: Optional[int] = None  # only when fog limits it
    wind_gl: str  # "dir/kts" at ground level
    wind_fl26: Optional[str] = None  # omitted when it matches the surface wind
    temp_c: int


class SituationView(BaseModel):
    turn: int
    date: str
    time_of_day: str
    weather: WeatherView
    campaign_state: Optional[str] = None  # only when not "ongoing"


class EconomyView(BaseModel):
    budget: int
    income_next_turn: int


class ControlPointView(BaseModel):
    id: str
    name: str
    type: str
    owner: str  # red / blue / neutral
    pos: list[float]
    sqns: Optional[int] = None
    parking_free: Optional[int] = None
    parking_total: Optional[int] = None
    can_recruit_ground: Optional[bool] = None
    factories: Optional[dict[str, str]] = None  # name -> alive / destroyed
    links: Optional[list[str]] = None  # adjacent control-point ids
    ground: Optional[dict[str, int]] = None  # armor on hand
    pending_ground: Optional[dict[str, int]] = None  # ordered, own bases only
    air: Optional[dict[str, dict[str, int]]] = None  # role -> {airframe: present}
    motorpool: Optional[int] = None  # reserve vehicles a strike here can reach
    can_launch: Optional[bool] = None  # False only; omitted when it can
    no_launch_reason: Optional[str] = None
    runway_repair_turns_remaining: Optional[int] = None


class SquadronView(BaseModel):
    id: str
    name: str
    aircraft: str
    base: str
    role: str  # the squadron's primary task
    tasks: list[str]  # every task the planner may give it on its own
    owned: Optional[int] = None
    # untasked/flyable are literal zeros once it owns aircraft: "none free" is news.
    untasked: Optional[int] = None
    flyable: Optional[int] = None
    pending: Optional[int] = None
    qra: Optional[int] = None  # held on intercept alert, outside the ATO
    pilots: int
    price: int
    max_ac: Optional[int] = None
    grounded: Optional[bool] = None
    unflyable: Optional[str] = None


class FlightView(BaseModel):
    id: str
    task: Optional[str]
    aircraft: str
    count: int
    squadron: str
    start: Optional[str] = None
    dep: Optional[str] = None
    clients: Optional[int] = None
    uncrewed: Optional[int] = None
    loadout: Optional[str] = None
    weapons: Optional[dict[int, str]] = None  # pylon -> weapon name, as flown
    startup_min: Optional[int] = None  # negative = the mission starts early for it
    tot_offset_min: Optional[float] = None  # vs the package TOT; negative = ahead


class PackageView(BaseModel):
    index: int
    target: str
    target_id: str
    target_kind: str  # base / ground_object / front / convoy / ship_convoy
    target_owner: Optional[str] = None  # red / blue: a BARCAP target is red's own
    task: Optional[str]
    tot: Optional[str]
    desc: Optional[str] = None
    flights: list[FlightView]


class TargetView(BaseModel):
    id: str
    name: str
    kind: str  # sam / ship / building / motorpool / front / convoy / cargo_ship / airfield
    suggested_task: str
    pos: list[float]
    category: Optional[str] = None  # buildings only
    base: Optional[str] = None
    threat_nm: Optional[int] = None
    detection_nm: Optional[int] = None
    friendly_cp_id: Optional[str] = None  # fronts: red's side
    enemy_cp_id: Optional[str] = None
    stance: Optional[str] = None  # fronts: red's current stance
    group_id: Optional[str] = None  # ships: their naval control point
    iads_role: Optional[str] = None
    composition: Optional[dict[str, int]] = None  # alive units per type
    origin: Optional[str] = None  # convoys and cargo ships
    destination: Optional[str] = None
    route: Optional[list[list[float]]] = None  # [start, end] of the leg it is moving
    damage: Optional[str] = None


class ThreatView(BaseModel):
    """A blue air-defense umbrella. Complete, ranked by reach: a top-N list reads as
    "these are the bubbles" and the rest get flown through."""

    id: str
    name: str
    kind: str
    threat_nm: int
    pos: list[float]


class IadsNodeView(BaseModel):
    id: str
    name: str
    role: str
    alive: bool
    depends_on: Optional[list[str]] = None


class IadsView(BaseModel):
    advanced: bool  # False = no power/comms wiring, only the sites matter
    nodes: list[IadsNodeView]


class NavalView(BaseModel):
    id: str
    name: str
    kind: str  # ship / carrier
    pos: list[float]
    move_range_nm: int
    destination: Optional[list[float]] = None
    threat_nm: Optional[int] = None
    damage: Optional[str] = None
    composition: Optional[dict[str, int]] = None


class RepairView(BaseModel):
    id: str
    name: str
    kind: str
    dead_units: Optional[int] = None


class GroundUnitView(BaseModel):
    name: str
    price: int
    kind: str  # front / artillery


class TurnContextView(BaseModel):
    side: str
    situation: SituationView
    economy: EconomyView
    control_points: list[ControlPointView]
    air_wing: list[SquadronView]
    idle_flyable: int
    targets: list[TargetView]
    threats: list[ThreatView]
    naval: list[NavalView]
    repairs: list[RepairView]
    buyable_ground: list[GroundUnitView]


class SideTurnView(BaseModel):
    aircraft: int
    vehicles: int  # armor held at bases


class TurnForcesView(BaseModel):
    """Force totals at the start of a past turn."""

    turn: int
    blue: SideTurnView
    red: SideTurnView


class LastTurnView(BaseModel):
    """The most recent flown turn, from the debrief (true numbers, both sides)."""

    turn: int
    blue_lost: dict[str, int]  # aircraft / front_line / sites
    red_lost: dict[str, int]
    blue_captured: Optional[list[str]] = None
    red_captured: Optional[list[str]] = None
    sorties: Optional[str] = None


class PrevTurnsView(BaseModel):
    trend: list[TurnForcesView]
    last_turn: Optional[LastTurnView] = None
    events: Optional[list[str]] = None  # the campaign log, sides named Blue and Red


class SettingView(BaseModel):
    key: str
    page: str
    section: str
    label: str
    value: Any
    detail: Optional[str] = None


class SettingsView(BaseModel):
    opfor_aggressiveness_pct: int
    map_coalition_visibility: str
    desired_player_mission_duration_min: int
    player_income_multiplier: float
    enemy_income_multiplier: float
    squadron_pilot_limit: Optional[int] = None  # omitted = no pilot limits
    pilot_replenishment_per_squadron: Optional[int] = None
    all_settings: list[SettingView]


# --- weather and situation ---

_CLOUD_COVERAGE = ((1, "FEW"), (4, "SCT"), (7, "BKN"), (11, "OVC"))


def _cloud_summary(clouds: Clouds) -> str:
    if clouds.preset is not None:
        # The description's first line is "##<name>"; the rest is a METAR breakdown.
        return clouds.preset.description.splitlines()[0].split("##")[-1].strip()
    for limit, name in _CLOUD_COVERAGE:
        if clouds.density < limit:
            return name
    return "OVC"


def _wind(wind: Wind) -> str:
    direction = str(wind.direction or 0).rjust(3, "0")
    return f"{direction}/{round(mps(wind.speed or 0).knots)}"


def build_weather(game: Game) -> WeatherView:
    weather = game.conditions.weather
    clouds = weather.clouds
    precip = None
    if clouds is not None and clouds.precipitation != PydcsWeather.Preceptions.None_:
        precip = clouds.precipitation.name.lower()
    vis_nm = None
    if weather.fog is not None:
        vis_nm = round(weather.fog.visibility.nautical_miles)
    surface = _wind(weather.wind.at_0m)
    high = _wind(weather.wind.at_8000m)
    return WeatherView(
        clouds="clear" if clouds is None else _cloud_summary(clouds),
        base_ft=None if clouds is None else round(meters(clouds.base).feet),
        precip=precip,
        vis_nm=vis_nm,
        wind_gl=surface,
        wind_fl26=None if high == surface else high,
        temp_c=round(weather.atmospheric.temperature_celsius),
    )


def build_situation(game: Game) -> SituationView:
    state = _CAMPAIGN_STATE_FROM_RED.get(game.check_win_loss().name, "ongoing")
    return SituationView(
        turn=game.turn,
        date=game.current_day.isoformat(),
        time_of_day=game.current_turn_time_of_day.name,
        weather=build_weather(game),
        campaign_state=None if state == "ongoing" else state,
    )


def build_economy(game: Game, side: str) -> EconomyView:
    player = player_for_side(side)
    return EconomyView(
        budget=round(game.coalition_for(player).budget),
        income_next_turn=round(Income(game, player).total),
    )


# --- control points ---


def _all_parking() -> Any:
    from game.theater.controlpoint import ParkingType

    return ParkingType(fixed_wing=True, fixed_wing_stol=True, rotary_wing=True)


def _parking(cp: ControlPoint) -> Optional[tuple[int, int]]:
    """(used, total) aircraft parking at a base, or None if it has none."""
    try:
        parking = _all_parking()
        total = cp.total_aircraft_parking(parking)
        if total <= 0:
            return None
        return total - cp.unclaimed_parking(parking), total
    except Exception:
        return None


def _motorpool_exposed(game: Game, cp: ControlPoint) -> Optional[int]:
    """Reserve vehicles that spawn in this base's strikeable motorpool (§56)."""
    try:
        from game.ground_forces.ai_ground_planner import reserve_armor_for
        from game.theater.theatergroundobject import MotorpoolGroundObject

        cap = game.settings.motorpool_spawn_cap
        if not game.settings.motorpool_enabled or cap <= 0:
            return None
        if not any(isinstance(t, MotorpoolGroundObject) for t in cp.ground_objects):
            return None
        return min(sum(reserve_armor_for(cp).values()), cap) or None
    except Exception:
        return None


def _pending_ground(cp: ControlPoint) -> dict[str, int]:
    try:
        orders = cp.ground_unit_orders.units
    except AttributeError:  # carriers and off-map points
        return {}
    return {ut.display_name: n for ut, n in orders.items() if n}


def _factories(cp: ControlPoint) -> Optional[dict[str, str]]:
    """A base recruits ground units only while one of its factories stands."""
    factories = {
        tgo.name: "destroyed" if tgo.is_dead() else "alive"
        for tgo in cp.connected_objectives
        if tgo.is_factory
    }
    return factories or None


def _air_intel(cp: ControlPoint) -> Optional[dict[str, dict[str, int]]]:
    """Aircraft on hand, by each squadron's primary task. The airframe's DCS default
    task filed SEAD Vipers and strike Phantoms alike under CAP."""
    by_role: dict[str, dict[str, int]] = {}
    for squadron in cp.squadrons:
        if not squadron.owned_aircraft:
            continue
        role = by_role.setdefault(squadron.primary_task.value, {})
        name = squadron.aircraft.display_name
        role[name] = role.get(name, 0) + squadron.owned_aircraft
    return by_role or None


def _no_launch_reason(cp: ControlPoint) -> str:
    """Three cases with three different answers; a FOB has no runway to crater."""
    from game.theater.controlpoint import Fob

    if isinstance(cp, Fob):
        return "no_launch_facilities"
    if not cp.runway_is_destroyable:
        return "hull_sunk"
    return "runway_damaged"


def build_control_point(
    game: Game, cp: ControlPoint, viewer: Optional[Player] = None
) -> ControlPointView:
    sqns = sum(1 for _ in cp.squadrons)
    park = _parking(cp)
    armor = cp.base.armor
    ground = {ut.display_name: n for ut, n in armor.items() if n}
    # The enemy's orders are hidden from the human too.
    pending_ground = _pending_ground(cp) if cp.captured == viewer else {}
    links = [str(n.id) for n in cp.connected_points] or None
    try:
        recruit = cp.has_ground_unit_source(game) or None
    except Exception:
        recruit = None
    operational = cp.runway_is_operational()
    try:
        repair_turns = cp.runway_status.repair_turns_remaining
    except Exception:  # carriers and off-map spawns have no runway status
        repair_turns = None
    return ControlPointView(
        id=str(cp.id),
        name=cp.name,
        type=cp.cptype.name,
        owner=cp.captured.name.lower(),
        pos=_latlng(game, cp.position.x, cp.position.y),
        sqns=sqns or None,
        parking_free=(park[1] - park[0]) if park else None,
        parking_total=park[1] if park else None,
        can_recruit_ground=recruit,
        factories=_factories(cp),
        links=links,
        ground=ground or None,
        pending_ground=pending_ground or None,
        air=_air_intel(cp),
        motorpool=_motorpool_exposed(game, cp),
        can_launch=False if not operational else None,
        no_launch_reason=None if operational else _no_launch_reason(cp),
        runway_repair_turns_remaining=repair_turns,
    )


# --- air wing ---


def _squadron_grounded(sq: Squadron, player: Optional[Player]) -> bool:
    if player is not None and sq.location.captured != player:
        return True
    return not sq.location.runway_is_operational()


def _squadron_flyable(sq: Squadron, grounded: bool) -> int:
    """min(untasked, pilots): untasked alone overstates what can launch."""
    if grounded or sq.untasked_aircraft <= 0:
        return 0
    if not sq.pilot_limits_enabled:
        return sq.untasked_aircraft
    return min(sq.untasked_aircraft, sq.number_of_available_pilots)


def _unflyable_reason(sq: Squadron, grounded: bool) -> Optional[str]:
    if not sq.owned_aircraft or _squadron_flyable(sq, grounded):
        return None
    if grounded:
        return "grounded"
    if sq.untasked_aircraft <= 0:
        if sq.intercept_reserve:
            return f"{sq.intercept_reserve} held on QRA alert, the rest tasked"
        return f"all {sq.owned_aircraft} already tasked"
    return "no available pilots"


def idle_flyable_total(game: Game, side: str) -> int:
    player = player_for_side(side)
    return sum(
        _squadron_flyable(sq, _squadron_grounded(sq, player))
        for sq in coalition_for_side(game, side).air_wing.iter_squadrons()
    )


def build_squadron(sq: Squadron, player: Optional[Player] = None) -> SquadronView:
    grounded = _squadron_grounded(sq, player)
    owned = sq.owned_aircraft
    return SquadronView(
        id=str(sq.id),
        name=str(sq),
        aircraft=sq.aircraft.display_name,
        base=sq.location.name,
        role=sq.primary_task.value,
        tasks=sorted(t.value for t in sq.auto_assignable_mission_types),
        owned=owned or None,
        untasked=sq.untasked_aircraft if owned else None,
        flyable=_squadron_flyable(sq, grounded) if owned else None,
        unflyable=_unflyable_reason(sq, grounded),
        pending=sq.pending_deliveries or None,
        qra=sq.intercept_reserve or None,
        pilots=sq.number_of_available_pilots,
        price=math.ceil(sq.aircraft.price),
        max_ac=sq.max_size if sq.settings.enable_squadron_aircraft_limits else None,
        grounded=grounded or None,
    )


# --- targets ---


def _damage_word(tgo: Any) -> Optional[str]:
    units = list(getattr(tgo, "units", []))
    if not units:
        return None
    alive = sum(1 for u in units if u.alive)
    if alive >= len(units):
        return None
    if alive == 0:
        return "destroyed"
    return "lightly damaged" if alive / len(units) > 0.6 else "heavily damaged"


def _unit_composition(tgo: Any) -> Optional[dict[str, int]]:
    """Alive units per type: a SAM with its TELs gone but its radar up reads as such."""
    comp: dict[str, int] = {}
    for unit in getattr(tgo, "units", []):
        if not unit.alive:
            continue
        unit_type = getattr(unit, "unit_type", None)
        name = getattr(unit_type, "display_name", None) or getattr(
            getattr(unit, "type", None), "name", None
        )
        if name:
            comp[str(name)] = comp.get(str(name), 0) + 1
    return comp or None


def _nm(distance_fn: Any) -> Optional[int]:
    try:
        distance = distance_fn()
    except Exception:
        return None
    return int(distance.nautical_miles) if distance else None


def _iads_role(tgo: TheaterGroundObject) -> Optional[str]:
    from game.theater.theatergroup import IadsGroundGroup

    for group in tgo.groups:
        if isinstance(group, IadsGroundGroup) and group.iads_role.participate:
            return str(group.iads_role.value)
    return None


def _build_target(
    game: Game, tgo: TheaterGroundObject, kind: str, task: str
) -> TargetView:
    group_id = None
    composition = None
    if kind == "ship":
        group_id = str(tgo.control_point.id)
        composition = _unit_composition(tgo)
    elif kind == "sam":
        composition = _unit_composition(tgo)
    return TargetView(
        id=str(tgo.id),
        name=tgo.name,
        kind=kind,
        suggested_task=task,
        pos=_latlng(game, tgo.position.x, tgo.position.y),
        category=tgo.category if kind == "building" else None,
        base=tgo.control_point.name if kind != "ship" else None,
        threat_nm=_nm(tgo.max_threat_range) or None,
        detection_nm=_nm(tgo.max_detection_range) or None,
        group_id=group_id,
        composition=composition,
        damage=_damage_word(tgo),
        iads_role=_iads_role(tgo),
    )


def _build_transport_targets(game: Game, player: Player) -> list[TargetView]:
    """Enemy convoys and cargo ships, as a base's Departing Convoys tab lists them.
    They have no id, so the generated name is the handle (unique for the turn)."""
    enemy = game.coalition_for(player).opponent
    out: list[TargetView] = []
    sources: tuple[tuple[Any, str, str], ...] = (
        (enemy.transfers.convoys, "convoy", "BAI"),
        (enemy.transfers.cargo_ships, "cargo_ship", "ANTISHIP"),
    )
    for transports, kind, task in sources:
        for transport in transports:
            units = {str(unit): n for unit, n in transport.units.items() if n}
            if not units:
                continue
            leg = getattr(transport, "route", None)
            if leg:
                ends = [_latlng(game, p.x, p.y) for p in (leg[0], leg[-1])]
            else:
                start, end = transport.route_start, transport.route_end
                ends = [_latlng(game, p.x, p.y) for p in (start, end)]
            out.append(
                TargetView(
                    id=transport.name,
                    name=transport.name,
                    kind=kind,
                    suggested_task=task,
                    pos=_latlng(game, transport.position.x, transport.position.y),
                    origin=transport.origin.name,
                    destination=transport.destination.name,
                    route=ends,
                    composition=units,
                )
            )
    return out


def _aircraft_on_hand(cp: ControlPoint) -> Optional[dict[str, int]]:
    """What an OCA/Aircraft strike here could catch on the ground."""
    on_hand: dict[str, int] = {}
    for squadron in cp.squadrons:
        if squadron.owned_aircraft:
            name = squadron.aircraft.display_name
            on_hand[name] = on_hand.get(name, 0) + squadron.owned_aircraft
    return on_hand or None


def build_targets(game: Game, side: str) -> list[TargetView]:
    from game.commander.objectivefinder import ObjectiveFinder

    player = player_for_side(side)
    finder = ObjectiveFinder(game, player)
    targets: list[TargetView] = []
    for sam in finder.enemy_air_defenses():
        targets.append(_build_target(game, sam, "sam", "DEAD"))
    for ship in finder.enemy_ships():
        targets.append(_build_target(game, ship, "ship", "ANTISHIP"))
    for building in finder.strike_targets():
        targets.append(_build_target(game, building, "building", "STRIKE"))
    for motorpool in finder.motorpool_targets():
        targets.append(_build_target(game, motorpool, "motorpool", "BAI"))
    targets.extend(_build_transport_targets(game, player))
    for cp in game.theater.controlpoints:
        if cp.captured == player.opponent and cp.runway_is_destroyable:
            targets.append(
                TargetView(
                    id=str(cp.id),
                    name=cp.name,
                    kind="airfield",
                    suggested_task="OCA_RUNWAY",
                    pos=_latlng(game, cp.position.x, cp.position.y),
                    composition=_aircraft_on_hand(cp),
                    damage=None if cp.runway_is_operational() else "runway closed",
                )
            )
    for front in game.theater.conflicts():
        friendly_cp = front.red_cp if player.is_red else front.blue_cp
        enemy_cp = front.blue_cp if player.is_red else front.red_cp
        stance = friendly_cp.stances.get(enemy_cp.id)
        targets.append(
            TargetView(
                id=str(front.id),
                name=front.name,
                kind="front",
                suggested_task="CAS",
                pos=_latlng(game, front.position.x, front.position.y),
                friendly_cp_id=str(friendly_cp.id),
                enemy_cp_id=str(enemy_cp.id),
                stance=stance.name if stance is not None else None,
            )
        )
    return targets


def build_own_sams(game: Game, side: str) -> list[TargetView]:
    """This side's live SAM sites, for drawing its own umbrellas on the map image."""
    from game.commander.objectivefinder import ObjectiveFinder
    from game.theater.theatergroundobject import IadsGroundObject

    finder = ObjectiveFinder(game, player_for_side(side))
    return [
        _build_target(game, go, "sam", "DEAD")
        for cp in finder.friendly_control_points()
        for go in cp.ground_objects
        if not go.is_dead() and isinstance(go, IadsGroundObject)
    ]


def build_own_ground_objects(game: Game, side: str) -> list[TargetView]:
    """This side's own sites, so a package aimed at one (a BARCAP over a SAM site)
    can be read. turn_context.targets is only ever the enemy's."""
    from game.theater.theatergroundobject import IadsGroundObject, ShipGroundObject

    player = player_for_side(side)
    out: list[TargetView] = []
    for cp in game.theater.controlpoints:
        if cp.captured != player:
            continue
        for go in cp.ground_objects:
            if go.is_dead():
                continue
            if isinstance(go, IadsGroundObject):
                kind = "sam"
            elif isinstance(go, ShipGroundObject):
                kind = "ship"
            else:
                kind = "building" if go.category else "ground"
            out.append(_build_target(game, go, kind, "BARCAP"))
    return out


def build_threats(targets: list[TargetView]) -> list[ThreatView]:
    ranked = sorted(
        (t for t in targets if t.kind in ("sam", "ship") and t.threat_nm),
        key=lambda t: t.threat_nm or 0,
        reverse=True,
    )
    return [
        ThreatView(
            id=t.id, name=t.name, kind=t.kind, threat_nm=t.threat_nm or 0, pos=t.pos
        )
        for t in ranked
    ]


# --- naval, repairs, ground buys ---


def _fleet_has_living_hull(cp: ControlPoint) -> bool:
    """A sunk flagship stops aviation, not the escorts: those still sail."""
    for tgo in cp.ground_objects:
        if tgo.is_control_point:
            return any(u.alive for u in tgo.units)
    return False


def _naval_view(game: Game, obj: Any, kind: str) -> NavalView:
    dest = None
    target_position = getattr(obj, "target_position", None)
    if target_position is not None:
        dest = _latlng(game, target_position.x, target_position.y)
    threat = None
    if callable(getattr(obj, "max_threat_range", None)):
        threat = _nm(obj.max_threat_range)
    comp = _unit_composition(obj)
    if comp is None:
        # A carrier's hulls live on its is_control_point ground object.
        for sub in getattr(obj, "ground_objects", []):
            if sub.is_control_point:
                comp = _unit_composition(sub)
                break
    return NavalView(
        id=str(obj.id),
        name=obj.name,
        kind=kind,
        pos=_latlng(game, obj.position.x, obj.position.y),
        move_range_nm=int(obj.max_move_distance.nautical_miles),
        destination=dest,
        threat_nm=threat or None,
        damage=_damage_word(obj),
        composition=comp,
    )


def build_my_naval(game: Game, side: str) -> list[NavalView]:
    from game.theater.theatergroundobject import ShipGroundObject

    player = player_for_side(side)
    out: list[NavalView] = []
    for cp in game.theater.controlpoints:
        if cp.captured != player:
            continue
        if cp.moveable and cp.is_fleet and _fleet_has_living_hull(cp):
            out.append(_naval_view(game, cp, "carrier"))
        for tgo in cp.ground_objects:
            if isinstance(tgo, ShipGroundObject) and tgo.moveable and not tgo.is_dead():
                out.append(_naval_view(game, tgo, "ship"))
    return out


def build_repairs(game: Game, side: str) -> list[RepairView]:
    """This side's damage that can be paid for: cratered runways and dead units."""
    player = player_for_side(side)
    out: list[RepairView] = []
    for cp in game.theater.controlpoints:
        if cp.captured != player:
            continue
        try:
            if cp.runway_can_be_repaired:
                out.append(RepairView(id=str(cp.id), name=cp.name, kind="runway"))
        except Exception:
            pass
        for tgo in cp.ground_objects:
            dead = [u for u in tgo.units if not u.alive and u.repairable]
            if dead:
                out.append(
                    RepairView(
                        id=str(tgo.id),
                        name=tgo.name,
                        kind=str(tgo.category or "ground"),
                        dead_units=len(dead),
                    )
                )
    return out


def build_buyable_ground(game: Game, side: str) -> list[GroundUnitView]:
    faction = coalition_for_side(game, side).faction
    out: list[GroundUnitView] = []
    for kind, units in (
        ("front", faction.frontline_units),
        ("artillery", faction.artillery_units),
    ):
        for unit in sorted(units, key=lambda u: u.display_name):
            out.append(
                GroundUnitView(
                    name=unit.display_name, price=math.ceil(unit.price), kind=kind
                )
            )
    return out


def build_turn_context(game: Game, side: str = "red") -> TurnContextView:
    side = side.lower()
    player = player_for_side(side)
    coalition = game.coalition_for(player)
    targets = build_targets(game, side)
    return TurnContextView(
        side=side,
        situation=build_situation(game),
        economy=build_economy(game, side),
        control_points=[
            build_control_point(game, cp, player) for cp in game.theater.controlpoints
        ],
        air_wing=[
            build_squadron(sq, player) for sq in coalition.air_wing.iter_squadrons()
        ],
        idle_flyable=idle_flyable_total(game, side),
        targets=targets,
        threats=build_threats(targets),
        naval=build_my_naval(game, side),
        repairs=build_repairs(game, side),
        buyable_ground=build_buyable_ground(game, side),
    )


# --- settings ---


def _setting_value(value: Any) -> Any:
    if isinstance(value, timedelta):
        return int(value.total_seconds() // 60)
    if isinstance(value, (bool, int, float, str)) or value is None:
        return value
    return getattr(value, "name", str(value))


def _all_settings(settings: Any) -> list[SettingView]:
    """Every setting in the order the settings dialog shows it."""
    from game.settings import Settings

    out: list[SettingView] = []
    for page in Settings.pages():
        for section in Settings.sections(page):
            for key, description in Settings.fields(page, section):
                out.append(
                    SettingView(
                        key=key,
                        page=page,
                        section=section,
                        label=description.text,
                        value=_setting_value(getattr(settings, key, None)),
                        detail=description.detail,
                    )
                )
    return out


def build_settings(game: Game) -> SettingsView:
    s = game.settings
    limits = s.enable_squadron_pilot_limits
    return SettingsView(
        opfor_aggressiveness_pct=s.opfor_autoplanner_aggressiveness,
        map_coalition_visibility=_setting_value(s.map_coalition_visibility),
        desired_player_mission_duration_min=int(
            s.desired_player_mission_duration.total_seconds() // 60
        ),
        player_income_multiplier=s.player_income_multiplier,
        enemy_income_multiplier=s.enemy_income_multiplier,
        squadron_pilot_limit=s.squadron_pilot_limit if limits else None,
        pilot_replenishment_per_squadron=(
            s.squadron_replenishment_rate if limits else None
        ),
        all_settings=_all_settings(s),
    )


# --- packages ---


def _flight_loadout(flight: Flight) -> tuple[Optional[str], Optional[dict[int, str]]]:
    member = next(iter(flight.iter_members()), None)
    if member is None:
        return None, None
    loadout = member.loadout
    game = flight.coalition.game
    if game.settings.restrict_weapons_by_date:
        # The fit the mission is built with (FlightGroupConfigurator.setup_payload):
        # the planned one lists weapons the date rule swaps out or drops.
        try:
            loadout = loadout.degrade_for_date(
                flight.unit_type,
                game.date,
                flight.squadron.coalition.faction,
                flight.package.target,
            )
        except Exception:
            pass
    weapons = {
        num: weapon.name for num, weapon in loadout.pylons.items() if weapon is not None
    }
    return loadout.name, weapons or None


def _startup_minutes(flight: Flight) -> Optional[int]:
    """Engine start in minutes from mission start, the clock TOTs are set on."""
    try:
        startup = flight.flight_plan.startup_time()
    except Exception:  # a flight without a plan yet
        return None
    mission_start = flight.coalition.game.conditions.start_time
    return round((startup - mission_start).total_seconds() / 60)


def _tot_offset_minutes(flight: Flight) -> Optional[float]:
    try:
        seconds = flight.flight_plan.tot_offset.total_seconds()
    except Exception:
        return None
    return round(seconds / 60, 1) or None


def build_flight(flight: Flight) -> FlightView:
    loadout_name, weapons = _flight_loadout(flight)
    return FlightView(
        id=str(flight.id),
        task=_enum_str(flight.flight_type),
        aircraft=flight.unit_type.display_name,
        count=flight.count,
        squadron=str(flight.squadron),
        start=_enum_str(flight.start_type),
        dep=flight.departure.name,
        clients=flight.client_count or None,
        uncrewed=flight.missing_pilots or None,
        loadout=loadout_name,
        weapons=weapons,
        startup_min=_startup_minutes(flight),
        tot_offset_min=_tot_offset_minutes(flight),
    )


def _target_kind(target: Any) -> str:
    from game.theater import ControlPoint, FrontLine, TheaterGroundObject
    from game.transfers import CargoShip

    if isinstance(target, ControlPoint):
        return "base"
    if isinstance(target, TheaterGroundObject):
        return "ground_object"
    if isinstance(target, FrontLine):
        return "front"
    if isinstance(target, CargoShip):
        return "cargo_ship"
    return "convoy"


def _target_id(target: Any) -> str:
    # Convoys and cargo ships have no id; turn_context names them instead.
    target_id = getattr(target, "id", None)
    return str(target_id) if target_id is not None else str(target.name)


def _target_owner(target: Any) -> Optional[str]:
    from game.theater import ControlPoint, TheaterGroundObject

    if isinstance(target, ControlPoint):
        return target.captured.name.lower()
    if isinstance(target, TheaterGroundObject):
        return target.control_point.captured.name.lower()
    return None


def build_package(index: int, package: Package) -> PackageView:
    tot = package.time_over_target
    target = package.target
    return PackageView(
        index=index,
        target=target.name,
        target_id=_target_id(target),
        target_kind=_target_kind(target),
        target_owner=_target_owner(target),
        task=_enum_str(package.primary_task),
        tot=tot.strftime("%H:%M") if tot else None,
        desc=package.package_description or None,
        flights=[build_flight(f) for f in package.flights],
    )


def build_packages(game: Game, side: str = "red") -> list[PackageView]:
    ato = coalition_for_side(game, side).ato
    return [build_package(i, p) for i, p in enumerate(ato.packages)]


def build_waypoints(game: Game, flight: Flight) -> list[dict[str, Any]]:
    waypoints: list[dict[str, Any]] = []
    for index, waypoint in enumerate(flight.flight_plan.waypoints):
        entry: dict[str, Any] = {
            "idx": index,
            "type": waypoint.waypoint_type.name,
            "pos": _latlng(game, waypoint.position.x, waypoint.position.y),
            "alt_ft": round(waypoint.alt.feet),
        }
        if waypoint.name:
            entry["name"] = waypoint.name
        # The plan's own schedule; waypoint.tot is only written at mission generation.
        plan = flight.flight_plan
        tot = plan.effective_tot_for_waypoint(waypoint) or (
            plan.chained_tot_for_waypoint(waypoint)
        )
        if tot is not None:
            entry["tot"] = tot.strftime("%H:%M:%S")
        waypoints.append(entry)
    return waypoints


# --- IADS ---


def build_iads(game: Game, side: str) -> IadsView:
    """The enemy's IADS graph. Dead nodes stay: a dead power station is what tells
    you the radars behind it are blind."""
    player = player_for_side(side)
    network = game.theater.iads_network
    nodes: list[IadsNodeView] = []
    for node in network.nodes:
        tgo = node.group.ground_object
        if tgo.is_friendly(player) or not node.group.iads_role.participate:
            continue
        depends = {
            str(conn.ground_object.id)
            for conn in node.connections.values()
            if conn.ground_object.id != tgo.id
        }
        nodes.append(
            IadsNodeView(
                id=str(tgo.id),
                name=tgo.name,
                role=str(node.group.iads_role.value),
                alive=node.group.alive_units() > 0,
                depends_on=sorted(depends) or None,
            )
        )
    return IadsView(advanced=network.advanced_iads, nodes=nodes)


# --- previous turns ---

#: The campaign log is written for the human: "we", "our" and "ally" are blue, "enemy"
#: and "OPFOR" are red. Red's reader gets the sides by name. "friendly" is left alone:
#: it means whichever side the line is about (ControlPoint.capture_equipment).
_LOG_SIDES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bWe have\b"), "Blue has"),
    (re.compile(r"\bWe\b"), "Blue"),
    (re.compile(r"\bOur\b"), "Blue's"),
    (re.compile(r"\bThe enemy\b"), "Red"),
    (re.compile(r"\b(?:Ally|Allied)\b"), "Blue"),
    (re.compile(r"\b(?:ally|allied)\b"), "blue"),
    (re.compile(r"\b(?:Enemy|OPFOR)\b"), "Red"),
    (re.compile(r"\benemy\b"), "red"),
)


def name_the_sides(line: str) -> str:
    for pattern, side in _LOG_SIDES:
        line = pattern.sub(side, line)
    return line


def build_prev_turns(game: Game, n: int = 3) -> PrevTurnsView:
    """The force trend over the last ``n`` turns, plus the last flown turn's debrief.

    The turn being planned already has a stats row but has not been flown, so it is
    left out: ``n=1`` should answer with the turn just fought.
    """
    data = game.game_stats.data_per_turn[: game.turn]
    start = max(0, len(data) - n)
    trend = [
        TurnForcesView(
            turn=i,
            blue=SideTurnView(
                aircraft=data[i].allied_units.aircraft_count,
                vehicles=data[i].allied_units.vehicles_count,
            ),
            red=SideTurnView(
                aircraft=data[i].enemy_units.aircraft_count,
                vehicles=data[i].enemy_units.vehicles_count,
            ),
        )
        for i in range(start, len(data))
    ]
    last_turn = None
    sitrep = game.last_sitrep
    if sitrep is not None:

        def losses(side: Any) -> dict[str, int]:
            return {
                "aircraft": side.aircraft,
                "front_line": side.front_line,
                "sites": side.sites,
            }

        last_turn = LastTurnView(
            turn=sitrep.turn,
            blue_lost=losses(sitrep.friendly),
            red_lost=losses(sitrep.enemy),
            blue_captured=list(sitrep.captured) or None,
            red_captured=list(sitrep.lost) or None,
            sorties=getattr(sitrep, "sortie_line", None),
        )
    events = [
        name_the_sides(f"{info.title}: {info.text}" if info.text else info.title)
        for info in game.informations
        if info.turn >= game.turn - 1
    ][-40:]
    return PrevTurnsView(trend=trend, last_turn=last_turn, events=events or None)
