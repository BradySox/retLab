from __future__ import annotations

import itertools
import logging
import math
from collections.abc import Iterator
from copy import deepcopy
from datetime import date, datetime, time, timedelta
from enum import Enum
from typing import Any, List, Optional, TYPE_CHECKING, Union, cast
from uuid import UUID, uuid4

from dcs.countries import (
    Switzerland,
    USAFAggressors,
    UnitedNationsPeacekeepers,
    country_dict,
)
from dcs.country import Country
from dcs.mapping import Point
from dcs.task import CAP, CAS, PinpointStrike
from dcs.vehicles import AirDefence

from game.ato.closestairfields import ObjectiveDistanceCache
from game.customkneeboard import CustomKneeboard
from game.ground_forces.ai_ground_planner import GroundPlanner
from game.models.game_stats import GameStats
from game.plugins import LuaPluginManager
from game.sitrep import Sitrep
from game.utils import Distance
from . import naming, persistency
from .ato.flighttype import FlightType
from .campaignloader import CampaignAirWingConfig
from .coalition import Coalition
from .db.gamedb import GameDb
from .dcs.countries import country_with_name
from .infos.information import Information
from .lasercodes.lasercoderegistry import LaserCodeRegistry
from .profiling import logged_duration
from .settings import NightMissions, Settings
from .data.groups import GroupTask
from .spatialindex import LiveUnitIndex
from .theater import ConflictTheater, Player
from .theater.supply import RECOVERY_MULTIPLIER, SupplyStatus, supply_statuses
from .theater.theatergroundobject import (
    EwrGroundObject,
    SamGroundObject,
    TheaterGroundObject,
)
from .theater.transitnetwork import TransitNetwork, TransitNetworkBuilder
from .timeofday import TimeOfDay
from .weather.conditions import Conditions

if TYPE_CHECKING:
    from .ato.airtaaskingorder import AirTaskingOrder
    from .retlab.flight_grades import FlightCard
    from .factions.faction import Faction
    from .retlab.super_gaggle import SuperGaggleCommitment
    from .retlab.victory import VictoryBaseline
    from .navmesh import NavMesh
    from .sim import GameUpdateEvents
    from .squadrons import AirWing
    from .theater.controlpoint import ControlPoint
    from .threatzones import ThreatZones

COMMISION_UNIT_VARIETY = 4
COMMISION_LIMITS_SCALE = 1.5
COMMISION_LIMITS_FACTORS = {
    PinpointStrike: 10,
    CAS: 5,
    CAP: 8,
    AirDefence: 8,
}

COMMISION_AMOUNTS_SCALE = 1.5
COMMISION_AMOUNTS_FACTORS = {
    PinpointStrike: 3,
    CAS: 1,
    CAP: 2,
    AirDefence: 0.8,
}

PLAYER_INTERCEPT_GLOBAL_PROBABILITY_BASE = 30
PLAYER_INTERCEPT_GLOBAL_PROBABILITY_LOG = 2
PLAYER_BASEATTACK_THRESHOLD = 0.4

# amount of strength player bases recover for the turn
PLAYER_BASE_STRENGTH_RECOVERY = 0.2

# Defined by upstream but never referenced: red bases have never recovered
# strength. Left as-is deliberately -- wiring it up is a balance change, not a
# supply rule, and the rung A gate can only ever reduce blue's free drift.
ENEMY_BASE_STRENGTH_RECOVERY = 0.05

# cost of AWACS for single operation
AWACS_BUDGET_COST = 4

# Bonus multiplier logarithm base
PLAYER_BUDGET_IMPORTANCE_LOG = 2


class TurnState(Enum):
    WIN = 0
    LOSS = 1
    CONTINUE = 2


class Game:
    scenery_clear_zones: List[Point]

    def __init__(
        self,
        player_faction: Faction,
        enemy_faction: Faction,
        theater: ConflictTheater,
        air_wing_config: CampaignAirWingConfig,
        start_date: datetime,
        start_time: time | None,
        settings: Settings,
        player_budget: float,
        enemy_budget: float,
        campaign_name: Optional[str] = None,
    ) -> None:
        self.settings = settings
        self.theater = theater
        self.campaign_name = campaign_name
        self.turn = 0
        # One-turn campaign summary (§29) captured at mission-results commit and
        # shown on the next turn's kneeboard cover band. None until the first
        # mission is flown; persisted.
        self.last_sitrep: Optional[Sitrep] = None
        #: §108: last mission's report cards, for the debrief.
        self.last_flight_cards: list[FlightCard] = []
        # Vietnam Ops Super Gaggle (§37): the turn's planned resupply run, drawn from real
        # BLUE squadrons; None when the feature is off or no gaggle is plannable. Losses are
        # charged back to the squadrons at debrief. Replanned each turn in finish_turn.
        self.super_gaggle_commitment: Optional["SuperGaggleCommitment"] = None
        # Custom victory conditions (§75): only the campaign-start strength
        # baseline + the announcement latch persist; condition definitions live
        # in the campaign YAML (+ the Settings knobs) and are re-derived, never
        # pickled. Evaluated at the turn boundary by check_win_loss.
        self.victory_baseline: Optional["VictoryBaseline"] = None
        self.victory_announced: set[str] = set()
        # W6 red tempo: the last turn resolve-regen was applied (idempotence
        # guard for the multiple-init-per-turn cases).
        self.red_tempo_regen_turn: Optional[int] = None
        # Red-tempo legibility: the last authored window whose "Hanoi's response"
        # was announced, so the message fires once per window (transient guard).
        self.red_tempo_announced_window: Optional[str] = None
        # COIN C1 per-CP regen anchors (garrison cap / cache total / fractional
        # carry), keyed by str(cp.id). Plain primitives so saves stay simple;
        # populated lazily by game.retlab.coin when coin_insurgency is on.
        self.coin_state: dict[str, dict[str, Any]] = {}
        # §50 convoy escort / ambush: this turn's ambush pairings ({"ambushes": [{tgo_id,
        # convoy}]}), seeded at finish_turn, read by the emitter + the escort auto-frag.
        # Plain primitives; populated lazily by game.retlab.convoy_ambush when on.
        self.convoy_ambush_state: dict[str, Any] = {}
        # §63 cruise missile raids: each LACM ship group's remaining missile stock,
        # keyed by the stable TheaterGroup.group_name — seeded on first sight, debited
        # at the turn boundary from what the plugin reports fired (never at
        # generation). Lazily populated by game.retlab.cruise_raids when
        # cruise_missile_strikes is on. There is no rearm.
        self.cruise_missile_magazines: dict[str, int] = {}
        # §81 cross-turn naval magazines: each naval group's remaining ANTI-SHIP
        # missile stock, keyed by the same stable TheaterGroup.group_name — seeded
        # on first sight, debited at the turn boundary from what the plugin reports
        # fired (never at generation). Lazily populated by
        # game.retlab.naval_magazines when naval_magazines is on. A disjoint
        # weapon set from the §63 magazine above, so the two never double-charge.
        # There is no rearm.
        self.naval_magazines: dict[str, int] = {}
        # Per-campaign secret salt for the §3 concealment jitter seed (id XOR salt),
        # so the jittered "suspected activity" centre is deterministic but not
        # recomputable from the public TGO id. Lazily set on first use; persisted.
        self.concealment_salt: Optional[int] = None
        # §97: a stable id for THIS game, so a lifetime pilot profile can tell a
        # replayed campaign's turn 1 from the one already flown -- the campaign
        # name and turn number alone cannot. Lazily set on first use; persisted.
        self.campaign_uid: Optional[str] = None
        # NB: This is the *start* date. It is never updated.
        self.date = date(start_date.year, start_date.month, start_date.day)
        self.game_stats = GameStats()
        self.notes = ""
        # §109: the outside AI's own notes between turns, saved with the campaign.
        # Whether it plans red is the setting outside_ai_plans_red.
        self.opfor_ai_notes: dict[str, str] = {}
        # Player-imported kneeboard images injected into client flights at mission
        # generation (managed in the UI; see game/customkneeboard.py).
        self.custom_kneeboards: list[CustomKneeboard] = []
        # Opaque JSON blob with the web client's map-layer panel state (which layers
        # are visible, base map, which groups are open). The client owns the
        # (de)serialization; the game just stores it so the choices travel with the
        # save instead of being lost on reload.
        self.client_map_layers: Optional[str] = None
        self.ground_planners: dict[UUID, GroundPlanner] = {}
        self.informations: list[Information] = []
        self.message("Game Start", "-" * 40)
        # Culling Zones are for areas around points of interest that contain things we may not wish to cull.
        self.__culling_zones: List[Point] = []
        self.__destroyed_units: list[dict[str, Union[float, str]]] = []
        self.savepath = ""
        self.current_unit_id = 0
        self.current_group_id = 0
        self.name_generator = naming.namegen
        self.laser_code_registry = LaserCodeRegistry()

        self.db = GameDb()

        if start_time is None:
            self.time_of_day_offset_for_start_time = list(TimeOfDay).index(
                TimeOfDay.Day
            )
        else:
            self.time_of_day_offset_for_start_time = list(TimeOfDay).index(
                self.theater.daytime_map.best_guess_time_of_day_at(start_time)
            )
        self.conditions = self.generate_conditions(forced_time=start_time)

        self.sanitize_sides(player_faction, enemy_faction)
        self.blue = Coalition(self, player_faction, player_budget, player=Player.BLUE)
        self.red = Coalition(self, enemy_faction, enemy_budget, player=Player.RED)
        neutral_faction = deepcopy(player_faction)
        neutral_faction.country = self.neutral_country
        self.neutral = Coalition(self, neutral_faction, 0, player=Player.NEUTRAL)
        self.blue.set_opponent(self.red)
        self.red.set_opponent(self.blue)

        for control_point in self.theater.controlpoints:
            control_point.finish_init(self)

        self.blue.configure_default_air_wing(air_wing_config)
        self.red.configure_default_air_wing(air_wing_config)

        self.on_load(game_still_initializing=True)

    def __setstate__(self, state: dict[str, Any]) -> None:
        state.setdefault("custom_kneeboards", [])
        state.setdefault("last_sitrep", None)
        # The §109 switch was a Game attribute until 2026-10-10; now a setting.
        if state.pop("opfor_ai_enabled", False):
            state["settings"].outside_ai_plans_red = True
        state.setdefault("opfor_ai_notes", {})
        state.setdefault("last_flight_cards", [])
        state.setdefault("client_map_layers", None)
        state.setdefault("super_gaggle_commitment", None)
        # W6 red tempo: pre-feature saves resolve on their next initialize_turn.
        state.setdefault("red_tempo_regen_turn", None)
        state.setdefault("red_tempo_announced_window", None)
        state.setdefault("coin_state", {})
        state.setdefault("convoy_ambush_state", {})
        state.setdefault("cruise_missile_magazines", {})
        state.setdefault("naval_magazines", {})
        state.setdefault("concealment_salt", None)
        state.setdefault("campaign_uid", None)
        # The political-will / war-economy meters (§48/§53) were removed; strip
        # their interim per-save state so it doesn't linger as dead attributes.
        state.pop("will_history", None)
        state.pop("will_ledger", None)
        # Drop-spawn (§20) was removed 2026-08-02 with game.theater.unitplacement;
        # a save with a queued placement carries a list of tombstone
        # PendingUnitPlacement placeholders. Nothing processes them anymore.
        state.pop("pending_unit_placements", None)
        self.__dict__.update(state)
        # Heal carcass lists bloated by old saves. Guarded like laser_code_registry
        # below: __destroyed_units postdates the oldest saves, so a pre-2020 save
        # arrives without it and must not AttributeError here.
        if hasattr(self, "_Game__destroyed_units"):
            self._dedup_destroyed_units()
        if not hasattr(self, "laser_code_registry"):
            self.laser_code_registry = LaserCodeRegistry()
            for front_line in self.theater.conflicts():
                front_line.laser_code = self.laser_code_registry.alloc_laser_code()
        # Regenerate any state that was not persisted.
        self.on_load()

    @property
    def coalitions(self) -> Iterator[Coalition]:
        yield self.blue
        yield self.red

    def point_in_world(self, x: float, y: float) -> Point:
        return Point(x, y, self.theater.terrain)

    def ato_for(self, player: Player) -> AirTaskingOrder:
        return self.coalition_for(player).ato

    def transit_network_for(self, player: Player) -> TransitNetwork:
        return self.coalition_for(player).transit_network

    def generate_conditions(self, forced_time: time | None = None) -> Conditions:
        return Conditions.generate(
            self.theater,
            self.current_day,
            self.current_turn_time_of_day,
            self.settings,
            forced_time=forced_time,
        )

    def advance_conditions(self) -> Conditions:
        """March the continuous campaign clock forward from this turn (§47)."""
        return Conditions.advance(self.conditions, self.theater, self.settings)

    @property
    def continuous_clock_active(self) -> bool:
        """Whether the continuous campaign clock/weather model is in effect.

        Gated by the `continuous_campaign_clock` setting, and only while the
        natural day/night cycle is allowed -- the OnlyDay/OnlyNight mission-time
        settings explicitly opt out of the natural cycle, so they fall back to
        the per-turn time-of-day rotation. `getattr` keeps pre-feature saves
        (no such setting) on the legacy path.
        """
        return (
            getattr(self.settings, "continuous_campaign_clock", False)
            and self.settings.night_day_missions == NightMissions.DayAndNight
        )

    @staticmethod
    def sanitize_sides(player_faction: Faction, enemy_faction: Faction) -> None:
        """
        Make sure the opposing factions are using different countries
        :return:
        """
        # TODO: This should just be rejected and sent back to the user to fix.
        # This isn't always something that the original faction can support.
        if player_faction.country == enemy_faction.country:
            if player_faction.country.name == "USA":
                enemy_faction.country = country_with_name("USAF Aggressors")
            elif player_faction.country.name == "Russia":
                enemy_faction.country = country_with_name("USSR")
            else:
                enemy_faction.country = country_with_name("Russia")

    def faction_for(self, player: Player) -> Faction:
        return self.coalition_for(player).faction

    def air_wing_for(self, player: Player) -> AirWing:
        return self.coalition_for(player).air_wing

    def repropagate_qra_reserves(self, old_ownfor: int, old_opfor: int) -> None:
        """Re-apply changed QRA-reserve defaults to existing squadrons."""
        self.blue.air_wing.repropagate_qra_reserve(
            old_ownfor, self.settings.ownfor_default_qra_reserve
        )
        self.red.air_wing.repropagate_qra_reserve(
            old_opfor, self.settings.opfor_default_qra_reserve
        )

    @property
    def neutral_country(self) -> Country:
        """Return the best fitting country to use for the neutral coalition.

        Returns the first candidate whose id is not already claimed by a
        belligerent. The in-use set spans every squadron's own country (#627
        per-squadron countries), not just the two faction primaries, so a CJTF
        side that fields e.g. a Swiss or UN squadron does not also hand that
        nation to the neutral coalition -- which would place one country on two
        coalitions (an unloadable .miz) and misfile neutral statics / break DCS
        capture triggers keyed on neutral membership. Membership is tested by id,
        which is pydcs's own equality key for ``Country`` (``Country.__eq__`` and
        ``__hash__`` are by ``id``).
        """
        ids_in_use = {self.red.faction.country.id, self.blue.faction.country.id}
        for coalition in (self.blue, self.red):
            for squadron in coalition.air_wing.iter_squadrons():
                ids_in_use.add(squadron.country.id)
        for candidate in (UnitedNationsPeacekeepers, Switzerland, USAFAggressors):
            if candidate.id not in ids_in_use:
                return candidate()
        # Every preferred neutral is claimed by a belligerent (e.g. a USAF
        # Aggressors red faction against a blue CJTF fielding UN and Swiss
        # squadrons). Returning a claimed country would place one nation on two
        # coalitions -- the unloadable .miz this property exists to prevent -- so
        # scan the full pydcs country list for any unclaimed nation instead.
        for country_id in sorted(country_dict):
            if country_id not in ids_in_use:
                return country_dict[country_id]()
        raise RuntimeError(
            "No neutral country available: every pydcs country is claimed by a "
            "belligerent"
        )

    def coalition_for(self, player: Player) -> Coalition:
        if player.is_neutral:
            return self.neutral
        elif player.is_blue:
            return self.blue
        else:
            return self.red

    def adjust_budget(self, amount: float, player: Player) -> None:
        self.coalition_for(player).adjust_budget(amount)

    def on_load(self, game_still_initializing: bool = False) -> None:
        from .sim import GameUpdateEvents

        if not hasattr(self, "name_generator"):
            self.name_generator = naming.namegen
        # Hack: Replace the global name generator state with the state from the save
        # game.
        #
        # We need to persist this state so that names generated after game load don't
        # conflict with those generated before exit.
        naming.namegen = self.name_generator
        LuaPluginManager.load_settings(self.settings)
        ObjectiveDistanceCache.set_theater(self.theater)
        self._rebuild_downed_pilot_index()
        self.compute_unculled_zones(GameUpdateEvents())
        # Apply mod settings again so mod properties get injected again,
        # in case mods like CJS F/A-18E/F/G or IDF F-16I are selected by the player
        self.blue.faction.apply_mod_settings()
        self.red.faction.apply_mod_settings()
        # The pickled ArmedForces would keep serving a mod preset group the
        # faction strip above removed (the buy menu and AI ground procurement
        # read it), so heal saves made before the strip caught the group.
        from game.factions.faction import disabled_mod_packages

        for coalition in (self.blue, self.red):
            faction_mod_settings = coalition.faction.mod_settings
            if faction_mod_settings is None:
                continue
            coalition.armed_forces.forces = [
                group
                for group in coalition.armed_forces.forces
                if not disabled_mod_packages(group, faction_mod_settings)
            ]
        if not game_still_initializing:
            # We don't need to push events that happen during load. The UI will fully
            # reset when we're done.
            self.compute_threat_zones(GameUpdateEvents())

    def _rebuild_downed_pilot_index(self) -> None:
        """Rebuilds the DownedPilot UUID lookup from the per-coalition lists.

        Both the coalition lists and the db index are pickled and share object
        references, so a normal load is already consistent. This makes the index
        authoritative regardless (e.g. for saves migrated from before CSAR).
        """
        if not hasattr(self, "db"):
            return
        self.db.downed_pilots.objects.clear()
        for coalition in (self.blue, self.red):
            for downed in coalition.downed_pilots:
                self.db.downed_pilots.objects[downed.id] = downed

    def finish_turn(self, events: GameUpdateEvents, skipped: bool = False) -> None:
        """Finalizes the current turn and advances to the next turn.

        This handles the turn-end portion of passing a turn. Initialization of the next
        turn is handled by `initialize_turn`. These are separate processes because while
        turns may be initialized more than once under some circumstances (see the
        documentation for `initialize_turn`), `finish_turn` performs the work that
        should be guaranteed to happen only once per turn:

        * Turn counter increment.
        * Delivering units ordered the previous turn.
        * Transfer progress.
        * Squadron replenishment.
        * Income distribution.
        * Base strength (front line position) adjustment.
        * Weather/time-of-day generation.

        Some actions (like transit network assembly) will happen both here and in
        `initialize_turn`. We need the network to be up to date so we can account for
        base captures when processing the transfers that occurred last turn, but we also
        need it to be up to date in the case of a re-initialization in `initialize_turn`
        (such as to account for a cheat base capture) so that orders are only placed
        where a supply route exists to the destination. This is a relatively cheap
        operation so duplicating the effort is not a problem.

        Args:
            skipped: True if the turn was skipped.
        """
        self.message("End of turn #" + str(self.turn), "-" * 40)
        self.turn += 1

        # The coalition-specific turn finalization *must* happen before unit deliveries,
        # since the coalition-specific finalization handles transit network updates and
        # transfer processing. If in the other order, units may be delivered to captured
        # bases, and freshly delivered units will spawn one leg through their journey.
        self.blue.end_turn(events)
        self.red.end_turn(events)

        for control_point in self.theater.controlpoints:
            control_point.process_turn(self, events)

        # Vietnam Ops convoy interdiction (§35): ensure the opfor has a *real*, tracked
        # convoy flowing on the trail corridor to interdict (replacing the old phantom
        # runtime spawn). Once per turn, after transfers are processed and the network is
        # current; a no-op unless the setting is on and a real corridor + spare rear units
        # exist. See game/retlab/vietnam_convoy.py.
        from game.retlab.vietnam_convoy import ensure_enemy_trail_convoy

        ensure_enemy_trail_convoy(self)

        # Ambient supply convoys (§50 standardization): keep a few randomized, real
        # columns flowing on BOTH sides' roads every mission -- some sharing a road,
        # some spread out -- so the theater has traffic to protect, hunt, and simply
        # see. Counts the §35 trail convoys above toward its target, so Vietnam's
        # trail war is unchanged. No-op unless ambient_supply_convoys is on, or for
        # a side with no same-side road. See game/retlab/ambient_convoys.py.
        from game.retlab.ambient_convoys import ensure_ambient_convoys

        ensure_ambient_convoys(self)

        # Convoy ambush (§50): roll each blue convoy for a CHANCE of an ambush --
        # 1..6 hidden red teams spread along its road (despawning last turn's first).
        # Nothing is telegraphed in the UI (map_hidden TGOs, no auto-fragged escort);
        # the player decides in-mission whether to support the column. No-op unless
        # convoy_ambush is on. Real units both sides -- losses track natively. See
        # game/retlab/convoy_ambush.py.
        from game.retlab.convoy_ambush import seed_convoy_ambushes

        seed_convoy_ambushes(self, events)

        # COIN C1 (design note retlab-coin-insurgent-replenishment-notes.md §3):
        # insurgent-held strongholds regenerate a free, cache-throttled trickle of
        # irregular units toward their anchored garrison cap. No-op unless
        # coin_insurgency is on. Real units via Base.commission_units -- losses
        # track natively; never a phantom spawn.
        from game.retlab.coin import (
            advance_reinfiltration,
            regenerate_insurgent_cells,
        )

        regenerate_insurgent_cells(self, events)
        # C1.5: the insurgency retakes cleared-but-unheld ground (a staged, announced,
        # counterable pipeline). Runs right after regen; gated coin_reinfiltration OFF.
        advance_reinfiltration(self, events)
        # COIN roadside IEDs: mine the insurgent ratline -- sweep it or the un-cleared
        # devices detonate on the coalition and drain the mandate. Gated coin_ied OFF.
        from game.retlab.coin_ied import advance_roadside_ieds

        advance_roadside_ieds(self, events)
        # COIN high-value targets: surface a named insurgent leader for a strike window
        # -- kill him inside it to blow the insurgency's momentum. Gated coin_hvt OFF.
        from game.retlab.coin_hvt import advance_hvt

        advance_hvt(self, events)
        # COIN dispersed cells: the insurgency in the open countryside -- patrol for them
        # or they coalesce into a stronghold and resupply its caches. Gated coin_dispersed
        # _cells OFF.
        from game.retlab.coin_dispersed import advance_dispersed_cells

        advance_dispersed_cells(self, events)

        # Vietnam Ops Super Gaggle (§37): (re)plan the turn's resupply run from real BLUE
        # squadrons (drawing the helos + suppressors from actual airframes, whose losses are
        # charged back at debrief), or clear it. No-op unless the setting is on and a besieged
        # outpost + launch field + a helo squadron with airframes all exist.
        from game.retlab.super_gaggle import plan_super_gaggle

        plan_super_gaggle(self)

        # Movable ship TGOs snap to their destination and re-parent to the
        # nearest friendly CP. Runs after captures are committed (process_results
        # precedes pass_turn -> finish_turn), so re-parenting sees post-capture
        # ownership.
        from game.theater.shipmovement import move_and_reparent_ships

        move_and_reparent_ships(self.theater.controlpoints)

        if not skipped:
            player_points = self.theater.player_points()
            # Rung A: reinforcement follows the roads. A base the enemy has cut
            # off rebuilds slowly or not at all instead of healing on a timer.
            statuses: dict[ControlPoint, SupplyStatus] = {}
            if self.settings.supply_gated_reinforcement:
                statuses = supply_statuses(player_points, self.blue.transit_network)
            for cp in player_points:
                for front_line in cp.front_lines.values():
                    front_line.settle_position()
                    events.update_front_line(front_line)
                status = statuses.get(cp)
                multiplier = 1.0 if status is None else RECOVERY_MULTIPLIER[status]
                cp.base.affect_strength(+PLAYER_BASE_STRENGTH_RECOVERY * multiplier)
        else:
            for front_line in self.theater.conflicts():
                front_line.hold_position()

        # After the first mission, reveal surviving MERAD groups. They start hidden
        # so players don't know enemy SA-6/11/17 positions before flying; the first
        # mission acts as intel gathering and they become visible from turn 2 onward.
        if self.turn == 1:
            self._reveal_merad_groups()

        # We don't actually advance time or change the conditions between turn 0 and
        # turn 1.
        if self.turn > 1:
            # Continuous campaign clock (§47): march the actual clock forward
            # from the previous turn and evolve the weather from its state so
            # the campaign flows as one timeline. Otherwise fall back to the
            # legacy per-turn time-of-day rotation + memoryless weather draw.
            if self.continuous_clock_active:
                self.conditions = self.advance_conditions()
            else:
                self.conditions = self.generate_conditions()

    def _reveal_merad_groups(self) -> None:
        for tgo in self.theater.ground_objects:
            if tgo.task == GroupTask.MERAD and tgo.hide_on_mfd:
                tgo.hide_on_mfd = False

    def begin_turn_0(self, squadrons_start_full: bool) -> None:
        """Initialization for the first turn of the game."""
        from .sim import GameUpdateEvents

        # A new campaign starts with the fog intact: the overview reveal is a
        # process global and must not carry over from a previous game.
        from .theater.fogofwar import set_fog_revealed

        set_fog_revealed(False)

        # Build the IADS Network
        with logged_duration("Generate IADS Network"):
            self.theater.iads_network.initialize_network(self.theater.ground_objects)

        for control_point in self.theater.controlpoints:
            control_point.initialize_turn_0(self.laser_code_registry)
            for tgo in control_point.connected_objectives:
                self.db.tgos.add(tgo.id, tgo)

        # Correct the heading of specifc TGOs, can only be done after init turn 0
        for tgo in self.theater.ground_objects:
            # If heading is 0 then we change the orientation to head towards the
            # closest conflict. Heading of 0 means that the campaign designer wants
            # to determine the heading automatically by liberation. Values other
            # than 0 mean it is custom defined.
            if tgo.should_head_to_conflict and tgo.heading.degrees == 0:
                # Calculate the heading to conflict
                heading = self.theater.heading_to_conflict_from(tgo.position)
                # Rotate the whole TGO with the new heading
                tgo.rotate(heading or tgo.heading)

        self.blue.preinit_turn_0(squadrons_start_full)
        self.red.preinit_turn_0(squadrons_start_full)

        # TODO: Check for overfull bases.
        # We don't need to actually stream events for turn zero because we haven't given
        # *any* state to the UI yet, so it will need to do a full draw once we do.
        self.initialize_turn(
            GameUpdateEvents(), squadrons_start_full=squadrons_start_full
        )

    def pass_turn(self, no_action: bool = False) -> None:
        """Ends the current turn and initializes the new turn.

        Called both when skipping a turn or by ending the turn as the result of combat.

        Args:
            no_action: True if the turn was skipped.
        """
        from .server import EventStream
        from .sim import GameUpdateEvents

        events = GameUpdateEvents()

        logging.info("Pass turn")
        with logged_duration("Turn finalization"):
            self.finish_turn(events, no_action)

        with logged_duration("Turn initialization"):
            self.initialize_turn(events)

        EventStream.put_nowait(events)

        # Autosave progress
        persistency.autosave(self)

    def check_win_loss(self) -> TurnState:
        # Alternate endings (§75 custom victory conditions) -- ONE evaluator
        # ahead of the stock capture-everything defaults: authored `victory:`
        # blocks + the domination/attrition knobs. Returns None when nothing is
        # configured, so this path costs nothing and the territory checks below
        # remain the universal fallback.
        from game.retlab.victory import victory_verdict

        alternate = victory_verdict(self)
        if alternate == "loss":
            return TurnState.LOSS
        if alternate == "win":
            return TurnState.WIN

        if not self.theater.player_points(state_check=True):
            return TurnState.LOSS

        if not self.theater.enemy_points(state_check=True):
            return TurnState.WIN

        return TurnState.CONTINUE

    def set_bullseye(self) -> None:
        blue_cp, red_cp = self.theater.bullseye_anchors()
        if self.blue.anchor_bullseye(red_cp, self.turn):
            logging.info(f"Blue bullseye re-anchored on {red_cp.name}")
        if self.red.anchor_bullseye(blue_cp, self.turn):
            logging.info(f"Red bullseye re-anchored on {blue_cp.name}")

    def initialize_turn(
        self,
        events: GameUpdateEvents,
        for_red: bool = True,
        for_blue: bool = True,
        squadrons_start_full: bool = False,
    ) -> None:
        """Performs turn initialization for the specified players.

        Turn initialization performs all of the beginning-of-turn actions. *End-of-turn*
        processing happens in `pass_turn` (despite the name, it's called both for
        skipping the turn and ending the turn after combat).

        Special care needs to be taken here because initialization can occur more than
        once per turn. A number of events can require re-initializing a turn:

        * Cheat capture. Bases changing hands invalidates many missions in both ATOs,
          purchase orders, threat zones, transit networks, etc. Practically speaking,
          after a base capture the turn needs to be treated as fully new. The game might
          even be over after a capture.
        * Cheat front line position. CAS missions are no longer in the correct location,
          and the ground planner may also need changes.
        * Selling/buying units at TGOs. Selling a TGO might leave missions in the ATO
          with invalid targets. Buying a new SAM (or even replacing some units in a SAM)
          potentially changes the threat zone and may alter mission priorities and
          flight planning.

        Most of the work is delegated to initialize_turn_for, which handles the
        coalition-specific turn initialization. In some cases only one coalition will be
        (re-) initialized. This is the case when buying or selling TGO units, since we
        don't want to force the player to redo all their planning just because they
        repaired a SAM, but should replan opfor when that happens. On the other hand,
        base captures are significant enough (and likely enough to be the first thing
        the player does in a turn) that we replan blue as well. Front lines are less
        impactful but also likely to be early, so they also cause a blue replan.

        Args:
            events: Game update event container for turn initialization.
            for_red: True if opfor should be re-initialized.
            for_blue: True if the player coalition should be re-initialized.
            squadrons_start_full: True if generator setting was checked.
        """
        # Check for win or loss condition FIRST!
        turn_state = self.check_win_loss()
        if turn_state in (TurnState.LOSS, TurnState.WIN):
            return self.process_win_loss(turn_state)

        # Update bullseye positions for blue & red
        self.set_bullseye()

        # Update statistics
        self.game_stats.update(self)

        # Plan flights & combat for next turn
        with logged_duration("Threat zone computation"):
            self.compute_threat_zones(events)

        # Custom victory conditions (§75): latch the campaign-start strength
        # baseline the ratio conditions measure against. Unconditional and
        # cheap, so a knob flipped on at turn 20 still measures against the
        # earliest state this build saw (turn 0 for a new game).
        from game.retlab.victory import ensure_victory_baseline

        ensure_victory_baseline(self)

        # Pin the COIN conservation anchors at the true campaign start (turn 0,
        # before any mission flies). The finish_turn regen hook runs after the
        # turn counter has advanced, so it can never take this snapshot itself.
        from game.retlab.coin import snapshot_campaign_start_anchors

        snapshot_campaign_start_anchors(self)

        # Plan Coalition specific turn
        if for_blue:
            self.blue.initialize_turn(self.turn == 0 and squadrons_start_full, events)
        if for_red:
            self.red.initialize_turn(self.turn == 0 and squadrons_start_full, events)

        # Sweep any stale "downed SOF team" objectives a pre-retirement save still
        # carries (the SOF capture economy was removed 2026-07-01; the objectives
        # were dynamic and are no longer rebuilt). No-op on current campaigns.
        from game.scar_rescue import purge_legacy_sof_state

        purge_legacy_sof_state(self)

        # W6 red tempo: during an authored ground-offensive pulse raise Hanoi's
        # front stances (after the coalitions plan, so it has the final say;
        # before GroundPlanner reads cp.stances) + apply any resolve regen.
        # Fully-guarded no-op without an active authored window.
        from game.retlab.red_tempo import apply_red_tempo

        apply_red_tempo(self)

        # Plan GroundWar
        self.ground_planners = {}
        for cp in self.theater.controlpoints:
            if cp.has_frontline:
                gplanner = GroundPlanner(cp, self)
                gplanner.plan_groundwar()
                self.ground_planners[cp.id] = gplanner

        # Update cull zones
        with logged_duration("Computing culling positions"):
            self.compute_unculled_zones(events)

        events.begin_new_turn()

    def message(self, title: str, text: str = "") -> None:
        self.informations.append(Information(title, text, turn=self.turn))

    @property
    def current_turn_time_of_day(self) -> TimeOfDay:
        # With the continuous clock (§47) the marched clock in `conditions` is
        # authoritative; time of day is derived from it. `getattr` guards the
        # init path, where `conditions` is not yet built (it seeds from the
        # legacy rotation below).
        if self.continuous_clock_active:
            conditions = getattr(self, "conditions", None)
            if conditions is not None:
                return conditions.time_of_day
        tod_turn = max(0, self.turn - 1) + self.time_of_day_offset_for_start_time
        return list(TimeOfDay)[tod_turn % 4]

    @property
    def current_day(self) -> date:
        # With the continuous clock (§47) the date follows the marched clock and
        # rolls over at midnight, instead of ticking once every four turns.
        if self.continuous_clock_active:
            conditions = getattr(self, "conditions", None)
            if conditions is not None:
                return conditions.start_time.date()
        return self.date + timedelta(days=self.turn // 4)

    def stable_uid(self) -> str:
        """This game's id, minted on first use and kept for its lifetime.

        §97 uses it to key the double-count guard on the GAME rather than the
        campaign name, so replaying a campaign logs its sorties again instead of
        being mistaken for the playthrough already recorded.
        """
        uid = getattr(self, "campaign_uid", None)
        if not uid:
            uid = str(uuid4())
            self.campaign_uid = uid
        return uid

    def next_unit_id(self) -> int:
        """
        Next unit id for pre-generated units
        """
        self.current_unit_id += 1
        return self.current_unit_id

    def next_group_id(self) -> int:
        """
        Next unit id for pre-generated units
        """
        self.current_group_id += 1
        return self.current_group_id

    def compute_transit_network_for(self, player: Player) -> TransitNetwork:
        return TransitNetworkBuilder(self.theater, player).build()

    def compute_threat_zones(self, events: GameUpdateEvents) -> None:
        self.blue.compute_threat_zones(events)
        self.red.compute_threat_zones(events)
        self.blue.compute_nav_meshes(events)
        self.red.compute_nav_meshes(events)

    def threat_zone_for(self, player: Player) -> ThreatZones:
        return self.coalition_for(player).threat_zone

    def navmesh_for(self, player: Player) -> NavMesh:
        return self.coalition_for(player).nav_mesh

    def compute_unculled_zones(self, events: GameUpdateEvents) -> None:
        """
        Compute the current conflict position(s) used for culling calculation
        """
        from game.missiongenerator.frontlineconflictdescription import (
            FrontLineConflictDescription,
        )

        zones = []

        # By default, use the existing frontline conflict position
        for front_line in self.theater.conflicts():
            position = FrontLineConflictDescription.frontline_position(
                front_line, self.theater, self.settings
            )
            zones.append(position[0])
            zones.append(front_line.blue_cp.position)
            zones.append(front_line.red_cp.position)

        for cp in self.theater.controlpoints:
            # If do_not_cull_carrier is enabled, add carriers as culling point
            if self.settings.perf_do_not_cull_carrier:
                if cp.is_carrier or cp.is_lha:
                    zones.append(cp.position)

        # If there is no conflict take the center point between the two nearest opposing bases
        if len(zones) == 0:
            cpoint = None
            min_distance = math.inf
            for cp in self.theater.player_points():
                for cp2 in self.theater.enemy_points():
                    d = cp.position.distance_to_point(cp2.position)
                    if d < min_distance:
                        min_distance = d
                        cpoint = cp.position.midpoint(cp2.position)
                        zones.append(cp.position)
                        zones.append(cp2.position)
                        break
                if cpoint is not None:
                    break
            if cpoint is not None:
                zones.append(cpoint)

        packages = itertools.chain(self.blue.ato.packages, self.red.ato.packages)
        for package in packages:
            if package.primary_task in [
                FlightType.BARCAP,
                FlightType.TRANSPORT,
                FlightType.AEWC,
                FlightType.REFUELING,
                FlightType.RECOVERY,
            ]:
                # BARCAPs will be planned at most locations on smaller theaters,
                # rendering culling fairly useless. BARCAP packages don't really
                # need the ground detail since they're defensive. SAMs nearby
                # are only interesting if there are enemies in the area, and if
                # there are they won't be culled because of the enemy's mission.

                # Don't create culling exclusion zones around FlightType.TRANSPORT,
                # FlightType.AEWC & FlightType.REFUELING mission targets.
                continue
            zones.append(package.target.position)

        # Cruise missile strikes (§63): the auto raid hits whatever the planner
        # picked — usually a rear-area object no package is fragged against, so
        # nothing else un-culls it. Without an exclusion zone the target TGO is
        # never generated and the missiles visibly demolish the *map's* scenery
        # at those coordinates while the campaign records nothing — a very
        # convincing no-op (flown and confirmed vs a culled refinery). Un-cull
        # every planned raid target, and every launching ship group so a
        # standalone LACM shooter always spawns for the F10 call-for-fire
        # (carrier groups are already covered by perf_do_not_cull_carrier).
        if getattr(self.settings, "cruise_missile_strikes", False):
            from game.retlab.cruise_raids import lacm_ships, plan_cruise_raids

            for raid in plan_cruise_raids(self):
                zones.append(Point(raid.target_x, raid.target_y, self.theater.terrain))
            for lacm_ship in lacm_ships(self):
                zones.append(lacm_ship.position)

        self.__culling_zones = zones
        events.update_unculled_zones(zones)

    @staticmethod
    def _carcass_key(data: dict[str, Union[float, str]]) -> tuple[str, int, int]:
        # (type, x, z) quantized to 1 m identifies one carcass. Statics that
        # Retribution respawns ALIVE each mission (FARP fuel/ammo depots,
        # motorpool Garage_A) fire a fresh S_EVENT_DEAD at the same deterministic
        # spot every time they are bombed; keying on this collapses them to a
        # single wreck. Type is in the key so adjacent different-type statics
        # (FARP fuel vs ammo) never merge; 1 m rounding absorbs Lua->JSON float
        # jitter (distinct same-type statics are always spaced well over a metre).
        # Precondition: data must carry "x" and "z" (raises KeyError otherwise).
        # For entries of unknown provenance use _safe_carcass_key instead.
        return (
            str(data.get("type", "")),
            round(cast(float, data["x"])),
            round(cast(float, data["z"])),
        )

    @staticmethod
    def _safe_carcass_key(
        data: dict[str, Union[float, str]],
    ) -> tuple[str, int, int] | None:
        # None for an unkeyable legacy entry (missing/garbled coords). Callers
        # treat None as "no match", so such entries are never merged nor crash
        # the dedup scan — matching _dedup's keep-them-untouched behaviour.
        # OverflowError: round(±inf); ValueError: round(nan); KeyError: no x/z;
        # TypeError: non-float coord.
        try:
            return Game._carcass_key(data)
        except (KeyError, TypeError, ValueError, OverflowError):
            return None

    def add_destroyed_units(self, data: dict[str, Union[float, str]]) -> None:
        pos = Point(
            cast(float, data["x"]), cast(float, data["z"]), self.theater.terrain
        )
        if not self.theater.is_on_land(pos):
            return
        # Bound to one carcass per (type, cell): a respawned-alive static bombed
        # every mission would otherwise stack a new hidden wreck each turn.
        # _safe_carcass_key throughout so a garbled coord (missing/inf/nan) never
        # crashes turn commit; an unkeyable entry (key None) can't be deduped, so
        # it's just recorded — mirroring _dedup's keep-them-untouched behaviour.
        key = self._safe_carcass_key(data)
        if key is not None and any(
            self._safe_carcass_key(d) == key for d in self.__destroyed_units
        ):
            return
        self.__destroyed_units.append(data)

    def get_destroyed_units(self) -> list[dict[str, Union[float, str]]]:
        return self.__destroyed_units

    def _dedup_destroyed_units(self) -> None:
        # Heal saves written before the insert-path dedup existed: collapse
        # stacked carcasses to one per (type, cell). First occurrence wins,
        # order preserved.
        seen: set[tuple[str, int, int]] = set()
        deduped: list[dict[str, Union[float, str]]] = []
        for d in self.__destroyed_units:
            key = self._safe_carcass_key(d)
            if key is None:
                deduped.append(d)  # unkeyable legacy entry: keep it, never dedup
                continue
            if key not in seen:
                seen.add(key)
                deduped.append(d)
        self.__destroyed_units = deduped

    def prune_destroyed_units(self, index: LiveUnitIndex) -> None:
        # Drop any carcass a live unit now occupies: once something alive stands at
        # a cell, its old wreck-history there is stale (the list is cosmetic-only).
        # Deleting (vs keeping-hidden) avoids two-husk stacking when a site is
        # rebuilt as a different type and re-killed. Garbled-coord entries can't be
        # matched, so they're kept — consistent with _safe_carcass_key.
        kept: list[dict[str, Union[float, str]]] = []
        for d in self.__destroyed_units:
            try:
                x = cast(float, d["x"])
                z = cast(float, d["z"])
                occupied = index.occupied(float(x), float(z))
            except (KeyError, TypeError, ValueError):
                # Missing x/z (KeyError) or a non-numeric coord (TypeError/
                # ValueError) -> unmatchable, keep the entry. Non-finite coords
                # don't reach here: LiveUnitIndex.occupied is total over floats.
                kept.append(d)
                continue
            if not occupied:
                kept.append(d)
        self.__destroyed_units = kept

    def position_culled(self, pos: Point) -> bool:
        """
        Check if unit can be generated at given position depending on culling performance settings
        :param pos: Position you are tryng to spawn stuff at
        :return: True if units can not be added at given position
        """
        if not self.settings.perf_culling:
            return False
        for z in self.__culling_zones:
            if z.distance_to_point(pos) < self.settings.perf_culling_distance * 1000:
                return False
        return True

    def iads_considerate_culling(self, tgo: TheaterGroundObject) -> bool:
        if not self.settings.perf_do_not_cull_threatening_iads:
            return self.position_culled(tgo.position)
        else:
            if self.settings.perf_culling:
                if isinstance(tgo, EwrGroundObject):
                    max_detection_range = tgo.max_detection_range().meters
                    for z in self.__culling_zones:
                        seperation = z.distance_to_point(tgo.position)
                        # Don't cull EWR if in detection range.
                        if seperation < max_detection_range:
                            return False
                if isinstance(tgo, SamGroundObject):
                    max_threat_range = tgo.max_threat_range().meters
                    for z in self.__culling_zones:
                        seperation = z.distance_to_point(tgo.position)
                        # Create a 12nm buffer around nearby SAMs.
                        respect_bubble = (
                            max_threat_range + Distance.from_nautical_miles(12).meters
                        )
                        if seperation < respect_bubble:
                            return False
            return self.position_culled(tgo.position)

    def get_culling_zones(self) -> list[Point]:
        """
        Check culling points
        :return: List of culling zones
        """
        return self.__culling_zones

    def process_win_loss(self, turn_state: TurnState) -> None:
        if turn_state is TurnState.WIN:
            self.message(
                "Congratulations, you are victorious! Start a new campaign to continue."
            )
        elif turn_state is TurnState.LOSS:
            self.message("Game Over, you lose. Start a new campaign to continue.")

    def ato_has_clients(self) -> bool:
        for package in self.blue.ato.packages:
            for flight in package.flights:
                if flight.client_count > 0:
                    return True
        return False
