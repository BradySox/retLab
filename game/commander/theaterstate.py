from __future__ import annotations

import dataclasses
import itertools
import math
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, TYPE_CHECKING, TypeVar, Union, Dict

from game.commander.battlepositions import BattlePositions
from game.commander.objectivefinder import ObjectiveFinder
from game.db import GameDb
from game.ground_forces.combat_stance import CombatStance
from game.htn import WorldState
from game.profiling import MultiEventTracer
from game.settings import Settings
from game.theater import (
    ConflictTheater,
    ControlPoint,
    FrontLine,
    MissionTarget,
    OffMapSpawn,
    Player,
)
from game.squadrons.downedpilot import DownedPilot
from game.theater.theatergroundobject import (
    BuildingGroundObject,
    IadsGroundObject,
    MotorpoolGroundObject,
    NavalGroundObject,
    TheaterGroundObject,
    VehicleGroupGroundObject,
)
from game.threatzones import ThreatZones
from game.utils import nautical_miles

if TYPE_CHECKING:
    from game import Game
    from game.coalition import Coalition
    from game.transfers import Convoy, CargoShip


@dataclass(frozen=True)
class PersistentContext:
    game_db: GameDb
    coalition: Coalition
    theater: ConflictTheater
    turn: int
    now: datetime
    settings: Settings
    tracer: MultiEventTracer


#: Key type of the BARCAP round counts trimmed by
#: :func:`trim_rounds_for_escort_reserve` (a control point in practice; the
#: function itself is key-agnostic).
_RoundsKeyT = TypeVar("_RoundsKeyT")


#: An LHA this close to a friendly carrier flies under the carrier's CAP.
LHA_CARRIER_CAP_COVER = nautical_miles(80)


def lha_covered_by_carrier(cp: ControlPoint, friendly: list[ControlPoint]) -> bool:
    """True for an LHA within ``LHA_CARRIER_CAP_COVER`` of a friendly carrier.

    Both ships got their own BARCAP stack over nearly the same point, which
    spent two flights on one patch of sky. A lone LHA keeps its own.
    """
    if not cp.is_lha:
        return False
    return any(
        other.is_carrier and cp.distance_to(other) <= LHA_CARRIER_CAP_COVER.meters
        for other in friendly
    )


def battle_position_bases(
    air_assault_points: Iterable[ControlPoint],
    front_lines: Iterable[FrontLine],
    player: Player,
) -> list[ControlPoint]:
    """The enemy bases the planner keeps battle positions for.

    The air-assault objectives, plus the enemy base of every front line.
    BreakthroughAttack looks its own front's base up, and air_assault_targets()
    drops a base more than 100 NM from ours: on a 116 NM front (Bardufoss to
    Alta) that lookup raised KeyError and the turn could not be planned.
    """
    bases = list(air_assault_points)
    for front_line in front_lines:
        base = front_line.control_point_hostile_to(player)
        if base not in bases:
            bases.append(base)
    return bases


def barcap_order(
    bases: Iterable[ControlPoint], enemy_bases: Iterable[ControlPoint]
) -> list[ControlPoint]:
    """BARCAP stations in the order the planner fills them.

    Carriers and LHAs first, then land bases nearest an enemy base first. The
    planner fills stations until the fighters run out, and in campaign-file
    order that put CAP 214 and 271 NM behind the front with none over the front
    fields (Crossing the Rubicon, 2026-10-10).
    """
    enemies = list(enemy_bases)

    def rank(base: ControlPoint) -> tuple[int, float]:
        if base.is_fleet:
            return 0, 0.0
        return 1, min((base.distance_to(enemy) for enemy in enemies), default=0.0)

    # dict.fromkeys: vulnerable_control_points yields a base once per threat.
    return sorted(dict.fromkeys(bases), key=rank)


def trim_rounds_for_escort_reserve(
    rounds: dict[_RoundsKeyT, int],
    available_fighters: int,
    reserve: int,
    jets_per_round: int = 2,
) -> dict[_RoundsKeyT, int]:
    """Free ~``reserve`` fighters from BARCAP volume when the pool is short.

    The ``Doctrine.strike_escort_reserve`` lever: the HTN plans BARCAP before
    any strike, so on fighter-poor eras (Vietnam) every airframe is committed
    by the time ``always_escort_strikes`` requests escorts, and they all prune
    -- B-52s fly naked through Linebacker. This trims BARCAP *demand* instead:
    drop one round at a time until the remaining demand fits under
    ``available - reserve``. Coverage thins to one round per location first; if
    even those floors are unaffordable, whole locations are abandoned (MiGCAP
    where it matters -- the era answer), but the first location always keeps a
    round.

    Locations are trimmed in the planner's own iteration order. An earlier
    revision ranked them by an air-threat score, but that threat field was part
    of the §6 air-defense rework and went away with it; the reserve guarantee
    (how many jets are freed) is unaffected -- only which location thins first.

    No-ops when the pool comfortably covers demand plus the reserve, and when
    the doctrine sets no reserve at all, so every non-Vietnam campaign keeps its
    full BARCAP volume. Pure and key-agnostic.
    """
    trimmed = dict(rounds)
    if reserve <= 0 or not trimmed:
        return trimmed
    demand = jets_per_round * sum(trimmed.values())
    if available_fighters >= demand + reserve:
        return trimmed
    # BARCAP planning consumes airframes until DEMAND or SUPPLY runs out, so
    # freeing jets means cutting demand BELOW supply-minus-reserve -- not
    # merely trimming `reserve`-worth of rounds off an oversubscribed total.
    affordable_rounds = max(0, available_fighters - reserve) // jets_per_round
    rounds_to_free = sum(trimmed.values()) - affordable_rounds
    protected = next(iter(trimmed))
    while rounds_to_free > 0:
        # Phase 1: thin everything to a one-round floor.
        candidates = [key for key, count in trimmed.items() if count > 1]
        if not candidates:
            # Phase 2: floors are still unaffordable -- abandon whole
            # locations, never the protected one.
            candidates = [
                key for key, count in trimmed.items() if count > 0 and key != protected
            ]
            if not candidates:
                break
        trimmed[candidates[-1]] -= 1
        rounds_to_free -= 1
    return trimmed


@dataclass
class TheaterState(WorldState["TheaterState"]):
    context: PersistentContext
    barcaps_needed: dict[ControlPoint, int]
    active_front_lines: list[FrontLine]
    front_line_stances: dict[FrontLine, Optional[CombatStance]]
    vulnerable_front_lines: list[FrontLine]
    aewc_targets: list[MissionTarget]
    refueling_targets: list[MissionTarget]
    recovery_targets: dict[ControlPoint, int]
    csar_targets: list[DownedPilot]
    #: Rescue packages committed so far this turn, capped by
    #: Settings.max_csar_flights. Counted rather than pre-trimming csar_targets so
    #: a pilot the planner *couldn't* reach (no aircraft, or a live SAM ring) does
    #: not consume one of the slots.
    csar_flights_planned: int
    enemy_air_defenses: list[IadsGroundObject]
    threatening_air_defenses: list[Union[IadsGroundObject, NavalGroundObject]]
    detecting_air_defenses: list[Union[IadsGroundObject, NavalGroundObject]]
    enemy_convoys: list[Convoy]
    enemy_shipping: list[CargoShip]
    enemy_ships: list[NavalGroundObject]
    enemy_battle_positions: dict[ControlPoint, BattlePositions]
    oca_targets: list[ControlPoint]
    strike_targets: list[TheaterGroundObject]
    motorpool_targets: list[MotorpoolGroundObject]
    enemy_barcaps: list[ControlPoint]
    threat_zones: ThreatZones
    vulnerable_control_points: list[ControlPoint]
    control_point_priority_queue: list[ControlPoint]
    priority_cp: Optional[ControlPoint]

    def _rebuild_threat_zones(self) -> None:
        """Recreates the theater's threat zones based on the current planned state."""
        self.threat_zones = ThreatZones.for_threats(
            self.context.theater,
            self.context.coalition.opponent.doctrine,
            barcap_locations=self.enemy_barcaps,
            air_defenses=itertools.chain(self.enemy_air_defenses, self.enemy_ships),
        )

    def eliminate_air_defense(self, target: IadsGroundObject) -> None:
        if target in self.threatening_air_defenses:
            self.threatening_air_defenses.remove(target)
        if target in self.detecting_air_defenses:
            self.detecting_air_defenses.remove(target)
        self.enemy_air_defenses.remove(target)
        self._rebuild_threat_zones()

    def eliminate_ship(self, target: NavalGroundObject) -> None:
        if target in self.threatening_air_defenses:
            self.threatening_air_defenses.remove(target)
        if target in self.detecting_air_defenses:
            self.detecting_air_defenses.remove(target)
        self.enemy_ships.remove(target)
        self._rebuild_threat_zones()

    def has_battle_position(self, target: VehicleGroupGroundObject) -> bool:
        return target in self.enemy_battle_positions[target.control_point]

    def eliminate_battle_position(self, target: VehicleGroupGroundObject) -> None:
        self.enemy_battle_positions[target.control_point].eliminate(target)

    def ammo_dumps_at(
        self, control_point: ControlPoint
    ) -> Iterator[BuildingGroundObject]:
        for target in self.strike_targets:
            if target.control_point != control_point:
                continue
            if target.is_ammo_depot:
                assert isinstance(target, BuildingGroundObject)
                yield target

    def clone(self) -> TheaterState:
        # Do not use copy.deepcopy. Copying every TGO, control point, etc is absurdly
        # expensive.
        return TheaterState(
            context=self.context,
            barcaps_needed=dict(self.barcaps_needed),
            active_front_lines=list(self.active_front_lines),
            front_line_stances=dict(self.front_line_stances),
            vulnerable_front_lines=list(self.vulnerable_front_lines),
            aewc_targets=list(self.aewc_targets),
            refueling_targets=list(self.refueling_targets),
            recovery_targets=dict(self.recovery_targets),
            csar_targets=list(self.csar_targets),
            csar_flights_planned=self.csar_flights_planned,
            enemy_air_defenses=list(self.enemy_air_defenses),
            enemy_convoys=list(self.enemy_convoys),
            enemy_shipping=list(self.enemy_shipping),
            enemy_ships=list(self.enemy_ships),
            enemy_battle_positions={
                cp: dataclasses.replace(g)
                for cp, g in self.enemy_battle_positions.items()
            },
            oca_targets=list(self.oca_targets),
            strike_targets=list(self.strike_targets),
            motorpool_targets=list(self.motorpool_targets),
            enemy_barcaps=list(self.enemy_barcaps),
            threat_zones=self.threat_zones,
            # Persistent properties are not copied. These are a way for failed subtasks
            # to communicate requirements to other tasks. For example, the task to
            # attack enemy battle_positions might fail because the target area has IADS
            # protection. In that case, the preconditions of PlanBai would fail, but
            # would add the IADS that prevented it from being planned to the list of
            # IADS threats so that DegradeIads will consider it a threat later.
            threatening_air_defenses=self.threatening_air_defenses,
            detecting_air_defenses=self.detecting_air_defenses,
            vulnerable_control_points=self.vulnerable_control_points,
            control_point_priority_queue=self.control_point_priority_queue,
            priority_cp=self.priority_cp,
        )

    @classmethod
    def from_game(
        cls, game: Game, player: Player, now: datetime, tracer: MultiEventTracer
    ) -> TheaterState:
        coalition = game.coalition_for(player)
        finder = ObjectiveFinder(game, player)
        ordered_capturable_points = finder.prioritized_points()
        air_assault_capturable_points = finder.air_assault_targets()

        context = PersistentContext(
            game.db,
            coalition,
            game.theater,
            game.turn,
            now,
            game.settings,
            tracer,
        )

        # Plan enough rounds of CAP that the target has coverage over the expected
        # mission duration. Waves overlap by barcap_overlap_time, so each wave only
        # contributes (duration - overlap) of *fresh* coverage; plan enough rounds
        # to span the mission even with overlapping handoffs.
        mission_duration = game.settings.desired_player_mission_duration.total_seconds()
        barcap_duration = game.settings.desired_barcap_mission_duration.total_seconds()
        barcap_overlap = game.settings.barcap_overlap_time.total_seconds()
        effective_coverage = max(barcap_duration - barcap_overlap, 60.0)
        barcap_rounds = math.ceil(mission_duration / effective_coverage)

        battle_postitions: Dict[ControlPoint, BattlePositions] = {
            cp: BattlePositions.for_control_point(cp)
            for cp in battle_position_bases(
                air_assault_capturable_points, finder.front_lines(), player
            )
        }

        # Air assault keeps its reach limit: a front-line base added above only
        # for the ground war is not an air-assault objective.
        vulnerable_control_points = [
            cp
            for cp in air_assault_capturable_points
            if not battle_postitions[cp].blocking_capture or cp.is_fleet
        ]

        aewc_targets = _aewc_targets(finder)

        enemy_air_defenses = list(finder.enemy_air_defenses())
        enemy_ships = list(finder.enemy_ships())

        friendly_cps = list(finder.friendly_control_points())
        enemy_bases = [
            cp
            for cp in finder.enemy_control_points()
            if not isinstance(cp, OffMapSpawn)
        ]
        barcaps_needed = {
            cp: 2 * barcap_rounds if cp.is_fleet else barcap_rounds
            for cp in barcap_order(finder.vulnerable_control_points(), enemy_bases)
            if not lha_covered_by_carrier(cp, friendly_cps)
        }
        # Strike-escort reserve (Doctrine.strike_escort_reserve): on fighter-poor
        # eras the HTN spends every fighter on BARCAP before any strike proposes
        # its escort, so always_escort_strikes prunes to nothing. Trim BARCAP
        # demand (never below one round at the first location) so ~reserve
        # airframes stay untasked for the escorts planned later this same run.
        # Zero for every doctrine except Vietnam, so this is a no-op elsewhere.
        escort_reserve = coalition.doctrine.strike_escort_reserve
        if escort_reserve > 0:
            available_fighters = coalition.air_wing.untasked_fighters()
            barcaps_needed = trim_rounds_for_escort_reserve(
                barcaps_needed,
                available_fighters,
                escort_reserve,
                # Worst-case BARCAP flight size (the fpa weights roll 2-4 ships):
                # the reserve is a guarantee, so budget rounds pessimistically --
                # under-trimming just re-starves the escorts (playtest-proven).
                jets_per_round=4,
            )

        return TheaterState(
            context=context,
            barcaps_needed=barcaps_needed,
            active_front_lines=list(finder.front_lines()),
            front_line_stances={f: None for f in finder.front_lines()},
            vulnerable_front_lines=list(finder.front_lines()),
            aewc_targets=list(aewc_targets),
            refueling_targets=_refueling_targets(finder),
            recovery_targets={cp: 0 for cp in finder.friendly_naval_control_points()},
            csar_targets=list(finder.downed_pilots()),
            csar_flights_planned=0,
            # RetLab: hoisted to a local above (reused for the threat-zone math),
            # so reuse the list instead of re-walking the finder.
            enemy_air_defenses=enemy_air_defenses,
            threatening_air_defenses=[],
            detecting_air_defenses=[],
            enemy_convoys=list(finder.convoys()),
            enemy_shipping=list(finder.cargo_ships()),
            enemy_ships=enemy_ships,
            enemy_battle_positions=battle_postitions,
            oca_targets=list(
                finder.oca_targets(
                    min_aircraft=game.settings.oca_target_autoplanner_min_aircraft_count
                )
            ),
            strike_targets=list(finder.strike_targets()),
            motorpool_targets=list(finder.motorpool_targets()),
            enemy_barcaps=list(game.theater.control_points_for(player.opponent)),
            threat_zones=game.threat_zone_for(player.opponent),
            vulnerable_control_points=vulnerable_control_points,
            control_point_priority_queue=ordered_capturable_points,
            priority_cp=(
                ordered_capturable_points[0] if ordered_capturable_points else None
            ),
        )


def _refueling_targets(finder: ObjectiveFinder) -> list[MissionTarget]:
    """One tanker station per friendly carrier, plus one land station.

    The stock single station was the CP nearest the enemy and asked nothing about
    basing, which stranded both of a flown Caucasus wing's tankers: the KC-135
    103 NM from its station and the carrier's A-6E 226 NM from its boat
    (test.retribution turn 2, 2026-08-19). A carrier's tanker belongs over its own
    boat -- the same shape AEW&C already uses -- and the land station goes to the
    most forward field that can actually put a tanker there.
    """
    targets: list[MissionTarget] = [
        cp for cp in finder.friendly_control_points() if cp.is_carrier
    ]
    _append_land_anchor(targets, finder.tanker_land_anchor())
    return targets


def _aewc_targets(finder: ObjectiveFinder) -> list[MissionTarget]:
    """One AEW&C target per friendly carrier, plus one land anchor.

    With an active front the land anchor is the rear-safe field hosting an
    AWACS, and the orbit is laid out relative to it -- the FLOT-anchored
    placement that used to override the target was reverted to upstream on
    2026-08-09 (§6, work order D). With NO front the orbit HOLDS at its target,
    so the rear pick would park the AWACS out of the war entirely -- the flown
    red A-50 orbited its rearmost home base 424 NM from the enemy fleet
    (2026-07-17 Scenic Route Merged; third campaign showing it). On a
    front-less theater the anchor is instead the friendly CP NEAREST the
    enemy: where the fight actually is -- but still one that HOSTS an AWACS, or
    the aircraft flies the theater to reach its own orbit (test 9: Ben Gurion
    picked, the only land E-3A at Akrotiri 164 NM away).
    """
    targets: list[MissionTarget] = [
        cp for cp in finder.friendly_control_points() if cp.is_carrier
    ]
    if any(True for _ in finder.front_lines()):
        _append_land_anchor(targets, finder.aewc_land_anchor())
    else:
        _append_land_anchor(targets, finder.forward_aewc_land_anchor())
    return targets


def _append_land_anchor(
    targets: list[MissionTarget], anchor: MissionTarget | None
) -> None:
    """Add the land station unless there is none or it is already a target.

    The planner consumes a target list one entry at a time and never dedupes it,
    so a repeat plans a second package on the identical anchor and flies a
    byte-identical racetrack. Latent, not flown: on brady.retribution turn 3 the old
    fallback returned CVN-71, already a carrier target, and only the hosting walk
    finding Incirlik first kept it out. None means the wing has no land field.
    """
    if anchor is None or any(anchor is target for target in targets):
        return
    targets.append(anchor)
