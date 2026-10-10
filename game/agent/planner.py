"""Write path for the outside AI planning red (§109 stage 2a).

Ported from juanjux/dcs-escalation `game/agent/planner.py` (LGPL-3), cut to packages,
TOTs, front stances and buying. The AI decides what; the engine's own
PackageFulfiller, flight-plan builders and purchase adapters decide how, so every plan
is one the scripted planner could have made. Every op reports per item instead of
raising, so one bad request never sinks a batch.
Design note: docs/dev/design/retlab-llm-opfor-notes.md.
"""

from __future__ import annotations

import contextlib
import math
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Iterator, Optional, TYPE_CHECKING, Union
from uuid import UUID

from game.agent import schemas, views
from game.ato.flighttype import FlightType
from game.commander.missionproposals import EscortType, ProposedFlight, ProposedMission
from game.commander.packagefulfiller import PackageFulfiller
from game.profiling import MultiEventTracer
from game.sim.missionstart import EARLY_START_CAP, launches_with_mission
from game.utils import meters, nautical_miles

if TYPE_CHECKING:
    from game import Game
    from game.ato import Package
    from game.squadrons import Squadron
    from game.theater import ControlPoint, MissionTarget


_ESCORTS = {
    "air": EscortType.AirToAir,
    "airtoair": EscortType.AirToAir,
    "escort": EscortType.AirToAir,
    "sead": EscortType.Sead,
    "dead": EscortType.Sead,
    "refuel": EscortType.Refuel,
    "tanker": EscortType.Refuel,
}

# Names a model reaches for that are not FlightType members.
_TASK_ALIASES = {
    "CAP": FlightType.BARCAP,
    "COMBAT_AIR_PATROL": FlightType.BARCAP,
}


def _flight_type(name: str) -> FlightType:
    raw = name.strip()
    key = raw.upper().replace(" ", "_").replace("-", "_")
    try:
        return FlightType[key]
    except KeyError:
        pass
    if key in _TASK_ALIASES:
        return _TASK_ALIASES[key]
    for flight_type in FlightType:
        if str(flight_type.value).upper() == raw.upper():
            return flight_type
    raise ValueError(f"unknown task {name!r}")


def _escort_type(name: Optional[str]) -> Optional[EscortType]:
    if not name:
        return None
    key = name.strip().lower().replace(" ", "").replace("-", "")
    try:
        return _ESCORTS[key]
    except KeyError:
        raise ValueError(f"unknown escort type {name!r}")


def _resolve_squadron(game: Game, side: str, squadron_id: str) -> Squadron:
    for squadron in views.coalition_for_side(game, side).air_wing.iter_squadrons():
        if str(squadron.id) == str(squadron_id):
            return squadron
    raise ValueError(f"no squadron with id {squadron_id!r}")


def _resolve_cp(game: Game, cp_id: str) -> ControlPoint:
    try:
        return game.theater.find_control_point_by_id(UUID(str(cp_id)))
    except (ValueError, KeyError, TypeError):
        raise ValueError(f"no control point with id {cp_id!r}")


def resolve_target(game: Game, target_id: str) -> MissionTarget:
    """A control point, ground object, front, or an enemy convoy or cargo ship by the
    name turn_context gives it (they have no id)."""
    for cp in game.theater.controlpoints:
        if str(cp.id) == target_id:
            return cp
        for tgo in cp.ground_objects:
            if str(tgo.id) == target_id:
                return tgo
    for front in game.theater.conflicts():
        if str(front.id) == target_id:
            return front
    for coalition in (game.blue, game.red):
        for transports in (
            coalition.transfers.convoys,
            coalition.transfers.cargo_ships,
        ):
            for transport in transports:
                if transport.name == target_id:
                    return transport
    raise ValueError(f"no target with id {target_id!r}")


def _free_aircraft_for(game: Game, side: str, spec: schemas.FlightSpec) -> int:
    if spec.squadron_id:
        try:
            return _resolve_squadron(game, side, spec.squadron_id).untasked_aircraft
        except ValueError:
            return 0
    try:
        task = _flight_type(spec.task)
    except ValueError:
        return 0
    squadrons = views.coalition_for_side(game, side).air_wing.iter_squadrons()
    return max(
        (s.untasked_aircraft for s in squadrons if s.capable_of(task)), default=0
    )


def _clamped_count(game: Game, side: str, spec: schemas.FlightSpec) -> int:
    """The player's flight creator caps a flight at min(free, max group size); an
    over-large flight otherwise generated only max_group_size units and lost the rest.
    """
    count = spec.count
    aircraft = None
    if spec.squadron_id:
        try:
            aircraft = _resolve_squadron(game, side, spec.squadron_id).aircraft
        except ValueError:
            aircraft = None
    if aircraft is None:
        from game.dcs.aircrafttype import AircraftType

        candidates = AircraftType.priority_list_for_task(_flight_type(spec.task))
        aircraft = candidates[0] if candidates else None
    if aircraft is not None:
        count = min(count, aircraft.max_group_size)
    available = _free_aircraft_for(game, side, spec)
    if available > 0:
        count = min(count, available)
    return max(1, count)


@contextlib.contextmanager
def _forced_task_assign(
    game: Game, side: str, spec: schemas.PackageSpec
) -> Iterator[None]:
    """A named squadron takes its task even if it is not auto-assignable for it, as a
    player assigning by hand would. Range, fuel and availability still apply."""
    added: list[tuple[Squadron, FlightType]] = []
    for flight in spec.flights:
        if not flight.squadron_id:
            continue
        try:
            squadron = _resolve_squadron(game, side, flight.squadron_id)
            task = _flight_type(flight.task)
        except ValueError:
            continue  # the diagnosis reports it
        if task not in squadron.auto_assignable_mission_types:
            squadron.auto_assignable_mission_types.add(task)
            added.append((squadron, task))
    try:
        yield
    finally:
        for squadron, task in added:
            squadron.auto_assignable_mission_types.discard(task)


def _proposed(
    game: Game, side: str, flights: list[schemas.FlightSpec]
) -> list[ProposedFlight]:
    out = []
    for spec in flights:
        squadron = (
            _resolve_squadron(game, side, spec.squadron_id)
            if spec.squadron_id
            else None
        )
        out.append(
            ProposedFlight(
                _flight_type(spec.task),
                _clamped_count(game, side, spec),
                _escort_type(spec.escort),
                preferred_type=squadron.aircraft if squadron else None,
                preferred_squadron=squadron,
            )
        )
    return out


def _flight_label(spec: schemas.FlightSpec) -> str:
    parts = [spec.task.upper()]
    if spec.squadron_id:
        parts.append(f"from {spec.squadron_id}")
    if spec.escort:
        parts.append(f"(escort {spec.escort})")
    return " ".join(parts)


def _diagnose_flights(
    game: Game, side: str, spec: schemas.PackageSpec
) -> list[Optional[str]]:
    """Per flight, why it cannot be filled, or None. Counts aircraft earlier flights in
    the same package already took, so two flights do not both claim the last jets."""
    squadrons = list(views.coalition_for_side(game, side).air_wing.iter_squadrons())
    try:
        target: Optional[MissionTarget] = resolve_target(game, spec.target_id)
    except ValueError:
        target = None
    used: dict[int, int] = defaultdict(int)
    out: list[Optional[str]] = []
    for flight in spec.flights:
        try:
            task = _flight_type(flight.task)
            _escort_type(flight.escort)
        except ValueError as exc:
            out.append(str(exc))
            continue
        count = _clamped_count(game, side, flight)
        if flight.squadron_id:
            try:
                squadron = _resolve_squadron(game, side, flight.squadron_id)
            except ValueError as exc:
                out.append(str(exc))
                continue
            if not squadron.capable_of(task):
                out.append(f"{squadron} can't fly {task.value}")
                continue
            candidates = [squadron]
        else:
            candidates = [s for s in squadrons if s.capable_of(task)]
            if not candidates:
                out.append("no airframe of this faction can fly this role")
                continue
        free = [s for s in candidates if s.untasked_aircraft - used[id(s)] >= count]
        if not free:
            most = max(
                (s.untasked_aircraft - used[id(s)] for s in candidates), default=0
            )
            out.append(
                f"needs {count} aircraft; the most any squadron has free is {most}"
            )
            continue
        assignable = next(
            (
                s
                for s in free
                if target is None
                or s.can_auto_assign_mission(
                    target, task, count, False, True, spec.ignore_range
                )
            ),
            None,
        )
        if assignable is None:
            out.append(_why_not_assignable(game, flight, free, task, count, target))
            continue
        used[id(assignable)] += count
        out.append(None)
    return out


def _why_not_assignable(
    game: Game,
    flight: schemas.FlightSpec,
    free: list[Squadron],
    task: FlightType,
    count: int,
    target: Optional[MissionTarget],
) -> str:
    if flight.escort:
        return "an escort attaches to the package's other flights and was not needed"
    if target is not None:
        for squadron in free:
            if squadron.can_auto_assign_mission(target, task, count, False, True, True):
                away = meters(target.distance_to(squadron.location)).nautical_miles
                limit = max(
                    squadron.aircraft.max_mission_range,
                    nautical_miles(game.settings.max_mission_range_planes),
                ).nautical_miles
                return (
                    f"out of the planner's range ({away:.0f} NM to the target, limit "
                    f"{limit:.0f} NM): set ignore_range to send it anyway"
                )
    return (
        "no free squadron will take this mission from its base (role, base type or "
        "crews); name one with squadron_id to force a capable one"
    )


def apply_tot_offset(flight: Any, minutes: float) -> None:
    flight.flight_plan.tot_offset = timedelta(minutes=float(minutes))


def _apply_tot_offsets(package: Package, specs: list[schemas.FlightSpec]) -> None:
    used: set[int] = set()
    for spec in specs:
        if spec.tot_offset_min is None:
            continue
        task = _flight_type(spec.task)
        for flight in package.flights:
            if id(flight) not in used and flight.flight_type == task:
                apply_tot_offset(flight, spec.tot_offset_min)
                used.add(id(flight))
                break


def earliest_tot_duration(package: Package) -> Optional[tuple[timedelta, str]]:
    """The slowest flight's start-to-TOT time, and its base. An ASAP TOT sits exactly
    on it. Asking for less builds the plan backwards past mission start, and the hold
    release timer goes negative, which DCS never fires."""
    worst: Optional[timedelta] = None
    where = ""
    for flight in package.flights:
        try:
            need = (
                flight.flight_plan.minimum_duration_from_start_to_tot()
                - flight.flight_plan.tot_offset
            )
        except Exception:
            continue
        if worst is None or need > worst:
            worst = need
            where = flight.departure.name
    return None if worst is None else (worst, where)


def earliest_tot_minutes(package: Package) -> Optional[tuple[int, str]]:
    duration = earliest_tot_duration(package)
    if duration is None:
        return None
    return math.ceil(duration[0].total_seconds() / 60), duration[1]


def early_start_reach(package: Package) -> timedelta:
    """How far before the turn clock this package's ground starts may begin (§104)."""
    return timedelta() if launches_with_mission(package) else EARLY_START_CAP


def tot_shortfall(
    package: Package, now: datetime, tot: Optional[datetime]
) -> Optional[tuple[int, str]]:
    """(earliest minute, base) when the package cannot make ``tot``. Compared in full
    precision with 30 s of grace: rounding read every ASAP package a minute late. A
    start the early mission start covers is not a shortfall: the scripted planner's
    own packages land there when a later package lengthens a field's runway queue."""
    duration = earliest_tot_duration(package)
    if duration is None or tot is None:
        return None
    needed, where = duration
    needed -= early_start_reach(package)
    if tot + timedelta(seconds=30) >= now + needed:
        return None
    return math.ceil(needed.total_seconds() / 60), where


def early_start_minutes(
    package: Package, now: datetime, tot: Optional[datetime]
) -> Optional[int]:
    """Minutes before the turn clock the mission must start for this package."""
    duration = earliest_tot_duration(package)
    if duration is None or tot is None or launches_with_mission(package):
        return None
    lead = now + duration[0] - tot - timedelta(seconds=30)
    if lead <= timedelta():
        return None
    cap = int(EARLY_START_CAP.total_seconds() // 60)
    return min(math.ceil(lead.total_seconds() / 60), cap)


def _apply_tot(package: Package, tot_minutes: Optional[int], now: datetime) -> None:
    if tot_minutes is None:
        package.auto_asap = True
        package.set_tot_asap(now)
        return
    package.auto_asap = False
    floor = earliest_tot_minutes(package)
    if floor is not None and tot_minutes < floor[0]:
        tot_minutes = floor[0]
    package.time_over_target = now + timedelta(minutes=tot_minutes)


def _mission_window_min(game: Game) -> int:
    return int(game.settings.desired_player_mission_duration.total_seconds() // 60)


def _within_window(tot_minutes: Optional[int], window: int) -> bool:
    return tot_minutes is not None and 0 <= tot_minutes <= window


def _push_new_package(package: Package) -> None:
    """Show the change on the live map, as the player's own edits do."""
    from game.server import EventStream
    from game.sim import GameUpdateEvents

    events = GameUpdateEvents()
    for flight in package.flights:
        events.new_flight(flight)
    EventStream.put_nowait(events)


def _push_removed_package(package: Package) -> None:
    from game.server import EventStream
    from game.sim import GameUpdateEvents

    EventStream.put_nowait(GameUpdateEvents().delete_flights_in_package(package))


def _plan(
    game: Game, side: str, spec: schemas.PackageSpec, flights: list[schemas.FlightSpec]
) -> Optional[Package]:
    coalition = views.coalition_for_side(game, side)
    target = resolve_target(game, spec.target_id)
    fulfiller = PackageFulfiller(
        coalition, game.theater, game.db.flights, game.settings
    )
    with MultiEventTracer() as tracer, _forced_task_assign(game, side, spec):
        return fulfiller.plan_mission(
            ProposedMission(target, _proposed(game, side, flights), asap=True),
            1,
            game.conditions.start_time,
            tracer,
            ignore_range=spec.ignore_range,
        )


def create_packages(
    game: Game, side: str, specs: list[Union[schemas.PackageSpec, dict[str, Any]]]
) -> list[schemas.CreateResult]:
    """One package per spec. Partial by default: flights that cannot be filled are left
    out and listed in ``dropped`` rather than scrubbing the whole package."""
    coalition = views.coalition_for_side(game, side)
    now = game.conditions.start_time
    results: list[schemas.CreateResult] = []
    for raw in specs:
        spec = (
            raw if isinstance(raw, schemas.PackageSpec) else schemas.PackageSpec(**raw)
        )
        target_name = spec.target_id
        try:
            target_name = resolve_target(game, spec.target_id).name
            with _forced_task_assign(game, side, spec):
                problems = _diagnose_flights(game, side, spec)
            keep = [f for f, p in zip(spec.flights, problems) if p is None]
            dropped = [
                schemas.DroppedFlight(flight=_flight_label(f), reason=p)
                for f, p in zip(spec.flights, problems)
                if p is not None
            ]
            if not keep:
                raise ValueError(
                    "could not fill any flight: "
                    + "; ".join(f"{d.flight}: {d.reason}" for d in dropped)
                )
            package = _plan(game, side, spec, keep)
            if package is None or not package.flights:
                raise ValueError("the planner could not fill this package")
            coalition.ato.add_package(package)
            try:
                _apply_tot_offsets(package, keep)
                _apply_tot(package, spec.tot_minutes, now)
                result = schemas.CreateResult(
                    ok=True,
                    target=target_name,
                    package=views.build_package(
                        len(coalition.ato.packages) - 1, package
                    ),
                    dropped=dropped or None,
                    idle_flyable_remaining=views.idle_flyable_total(game, side),
                )
            except Exception:
                # The package already holds its aircraft and pilots; removing it hands
                # them back, so an error always means nothing was added.
                coalition.ato.remove_package(package)
                raise
            _push_new_package(package)
            results.append(result)
        except Exception as exc:
            results.append(
                schemas.CreateResult(ok=False, target=target_name, error=str(exc))
            )
    return results


def evaluate_package(
    game: Game, side: str, spec: schemas.PackageSpec
) -> schemas.EvaluateResult:
    """Plan a package, read it, and roll it back."""
    coalition = views.coalition_for_side(game, side)
    now = game.conditions.start_time
    target_name = spec.target_id
    try:
        target_name = resolve_target(game, spec.target_id).name
        package = _plan(game, side, spec, list(spec.flights))
        if package is None or not package.flights:
            with _forced_task_assign(game, side, spec):
                problems = [p for p in _diagnose_flights(game, side, spec) if p]
            raise ValueError("; ".join(problems) or "the planner could not fill it")
        # plan_mission claims the aircraft; adding then removing hands them back.
        coalition.ato.add_package(package)
        try:
            _apply_tot_offsets(package, list(spec.flights))
            _apply_tot(package, spec.tot_minutes, now)
            tot = package.time_over_target
            tot_min = round((tot - now).total_seconds() / 60)
            window = _mission_window_min(game)
            return schemas.EvaluateResult(
                ok=True,
                target=target_name,
                package=views.build_package(-1, package),
                tot_minutes_into_mission=tot_min,
                mission_window_min=window,
                within_window=_within_window(tot_min, window),
            )
        finally:
            coalition.ato.remove_package(package)
    except Exception as exc:
        return schemas.EvaluateResult(ok=False, target=target_name, error=str(exc))


def validate_plan(game: Game, side: str) -> schemas.ValidateResult:
    """Every package's TOT against the mission window and its reach, and its crews."""
    coalition = views.coalition_for_side(game, side)
    window = _mission_window_min(game)
    now = game.conditions.start_time
    checks: list[schemas.PackageCheck] = []
    issues: list[str] = []
    notes: list[str] = []
    for i, package in enumerate(coalition.ato.packages):
        view = views.build_package(i, package)
        tot = package.time_over_target
        tot_min = round((tot - now).total_seconds() / 60)
        within = _within_window(tot_min, window)
        uncrewed = sum(f.uncrewed or 0 for f in view.flights)
        if uncrewed:
            issues.append(f"#{i} {view.target}: {uncrewed} seats without a pilot")
        if not within:
            # The scripted planner's own long-range raids land here; not a fault.
            notes.append(
                f"#{i} {view.target}: TOT +{tot_min} min is after the {window} min "
                f"the human plans to fly"
            )
        shortfall = tot_shortfall(package, now, tot)
        early = None
        if shortfall is not None:
            issues.append(
                f"#{i} {view.target}: TOT +{tot_min} min cannot be made from "
                f"{shortfall[1]}; the earliest is +{shortfall[0]}"
            )
        else:
            early = early_start_minutes(package, now, tot)
            if early:
                notes.append(
                    f"#{i} {view.target}: the mission starts {early} min early so "
                    f"this package makes its TOT"
                )
        checks.append(
            schemas.PackageCheck(
                index=i,
                target=view.target,
                tot=view.tot,
                tot_minutes_into_mission=tot_min,
                within_window=within,
                uncrewed=uncrewed or None,
                earliest_tot_minutes=shortfall[0] if shortfall else None,
                starts_mission_early_min=early,
            )
        )
    idle = views.idle_flyable_total(game, side)
    if idle:
        notes.append(f"{idle} flyable aircraft have no task")
    return schemas.ValidateResult(
        ok=not issues,
        mission_window_min=window,
        packages=checks,
        issues=issues or None,
        notes=notes or None,
    )


def _package_at(game: Game, side: str, index: int) -> Package:
    packages = views.coalition_for_side(game, side).ato.packages
    if not 0 <= index < len(packages):
        raise ValueError(f"no package at index {index}")
    return packages[index]


def set_package_tot(
    game: Game, side: str, index: int, tot_minutes: Optional[int]
) -> schemas.OpResult:
    try:
        package = _package_at(game, side, index)
        _apply_tot(package, tot_minutes, game.conditions.start_time)
        tot_min = round(
            (package.time_over_target - game.conditions.start_time).total_seconds() / 60
        )
        if tot_minutes is None:
            detail = f"package {index} TOT is ASAP (+{tot_min} min)"
        elif tot_min > tot_minutes:
            detail = (
                f"package {index}: +{tot_minutes} min cannot be made; set to the "
                f"earliest, +{tot_min} min"
            )
        else:
            detail = f"package {index} TOT set to +{tot_min} min"
        return schemas.OpResult(ok=True, detail=detail)
    except ValueError as exc:
        return schemas.OpResult(ok=False, error=str(exc))


def delete_package(game: Game, side: str, index: int) -> schemas.OpResult:
    """Remove a package; its aircraft and pilots go back to their squadrons."""
    try:
        package = _package_at(game, side, index)
        views.coalition_for_side(game, side).ato.remove_package(package)
        _push_removed_package(package)
        return schemas.OpResult(ok=True, detail=f"removed package {index}")
    except ValueError as exc:
        return schemas.OpResult(ok=False, error=str(exc))


def clear_packages(game: Game, side: str) -> schemas.OpResult:
    ato = views.coalition_for_side(game, side).ato
    packages = list(ato.packages)
    for package in packages:
        ato.remove_package(package)
        _push_removed_package(package)
    return schemas.OpResult(ok=True, detail=f"removed {len(packages)} packages")


def _purchase_limits(game: Game, side: str, squadron: Squadron) -> str:
    """Which limit refused a buy: base parking, the squadron cap, or the budget."""
    from game.theater.controlpoint import ParkingType

    cp = squadron.location
    parking = ParkingType().from_squadron(squadron)
    parts = [
        f"{cp.name} parking {cp.unclaimed_parking(parking)} free of "
        f"{cp.total_aircraft_parking(parking)} (shared by its squadrons)",
        f"budget {round(views.coalition_for_side(game, side).budget)}, "
        f"{math.ceil(squadron.aircraft.price)} each",
    ]
    if squadron.settings.enable_squadron_aircraft_limits:
        parts.insert(
            1,
            f"squadron {squadron.owned_aircraft}+{squadron.pending_deliveries} of "
            f"max {squadron.max_size}",
        )
    return "; ".join(parts)


def buy_aircraft(
    game: Game, side: str, squadron_id: str, quantity: int
) -> schemas.OpResult:
    """Order aircraft into a squadron; they arrive next turn."""
    from game.purchaseadapter import AircraftPurchaseAdapter, TransactionError

    try:
        squadron = _resolve_squadron(game, side, squadron_id)
        if squadron.location.captured != views.player_for_side(side):
            raise ValueError(f"{squadron.location.name} is not yours")
        try:
            AircraftPurchaseAdapter(squadron.location).buy(squadron, quantity)
        except TransactionError as exc:
            raise ValueError(f"{exc}: {_purchase_limits(game, side, squadron)}")
        budget = round(views.coalition_for_side(game, side).budget)
        return schemas.OpResult(
            ok=True,
            detail=f"ordered {quantity} {squadron.aircraft.display_name} for "
            f"{squadron}; budget now {budget}",
        )
    except ValueError as exc:
        return schemas.OpResult(ok=False, error=str(exc))


def sell_aircraft(
    game: Game, side: str, squadron_id: str, quantity: int
) -> schemas.OpResult:
    """Sell untasked aircraft, or cancel aircraft on order, for a refund."""
    from game.purchaseadapter import AircraftPurchaseAdapter, TransactionError

    try:
        squadron = _resolve_squadron(game, side, squadron_id)
        AircraftPurchaseAdapter(squadron.location).sell(squadron, quantity)
        budget = round(views.coalition_for_side(game, side).budget)
        return schemas.OpResult(
            ok=True,
            detail=f"sold {quantity} {squadron.aircraft.display_name} from "
            f"{squadron}; budget now {budget}",
        )
    except (TransactionError, ValueError) as exc:
        return schemas.OpResult(ok=False, error=str(exc))


def buy_ground(
    game: Game, side: str, cp_id: str, unit_name: str, quantity: int
) -> schemas.OpResult:
    """Order ground units at a base; they arrive next turn."""
    from game.purchaseadapter import GroundUnitPurchaseAdapter, TransactionError

    coalition = views.coalition_for_side(game, side)
    try:
        cp = _resolve_cp(game, cp_id)
        if cp.captured != views.player_for_side(side):
            raise ValueError(f"{cp.name} is not yours")
        buyable = coalition.faction.frontline_units | coalition.faction.artillery_units
        unit = next(
            (u for u in buyable if unit_name in (u.display_name, u.variant_id)), None
        )
        if unit is None:
            raise ValueError(f"{unit_name!r} is not a ground unit this faction buys")
        if not cp.has_ground_unit_source(game):
            raise ValueError(f"{cp.name} cannot recruit ground units")
        GroundUnitPurchaseAdapter(cp, coalition, game).buy(unit, quantity)
        return schemas.OpResult(
            ok=True,
            detail=f"ordered {quantity} {unit.display_name} at {cp.name}; budget now "
            f"{round(coalition.budget)}",
        )
    except (TransactionError, ValueError) as exc:
        return schemas.OpResult(ok=False, error=str(exc))


def set_stance(
    game: Game, side: str, friendly_cp_id: str, enemy_cp_id: str, stance: str
) -> schemas.OpResult:
    from game.ground_forces.combat_stance import CombatStance

    aliases = {
        "defend": CombatStance.DEFENSIVE,
        "hold": CombatStance.DEFENSIVE,
        "push": CombatStance.AGGRESSIVE,
        "eliminate": CombatStance.ELIMINATION,
    }
    try:
        friendly = _resolve_cp(game, friendly_cp_id)
        enemy = _resolve_cp(game, enemy_cp_id)
        if friendly.captured != views.player_for_side(side):
            raise ValueError(f"{friendly.name} is not yours")
        if enemy.id not in friendly.stances:
            raise ValueError(f"{friendly.name} has no front with {enemy.name}")
        key = stance.strip()
        chosen = aliases.get(key.lower())
        if chosen is None:
            try:
                chosen = CombatStance[key.upper()]
            except KeyError:
                names = ", ".join(s.name for s in CombatStance)
                raise ValueError(f"unknown stance {stance!r}; one of {names}")
        friendly.stances[enemy.id] = chosen
        return schemas.OpResult(
            ok=True, detail=f"{friendly.name} against {enemy.name}: {chosen.name}"
        )
    except ValueError as exc:
        return schemas.OpResult(ok=False, error=str(exc))
