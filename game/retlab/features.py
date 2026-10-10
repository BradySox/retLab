"""RetLab feature registry — one self-describing entry per feature.

The fork carries ~30 features layered on upstream Retribution. The "what features
exist and how is each wired" knowledge (which Lua plugin runs it, which
``Settings`` toggle gates it, which features-doc section documents it) used to live
only in prose that drifts as code changes. This module makes it a *data structure*
that the docs and CI are checked against:

* Every numbered feature in the CLAUDE.md "Features at a Glance" list is a
  :class:`Feature` in :data:`FEATURES` (plus the always-on engine plugins).
* :func:`render_feature_index` renders the registry to the committed Markdown
  catalog ``docs/dev/retlab-feature-index.md``.
* ``tests/retlab/test_features_registry.py`` makes drift a CI failure: every
  plugin/``Settings`` reference must resolve, the registry must cover exactly the
  numbered feature list, every in-game-pass checklist ``§N`` must be registered,
  and the generated catalog must be current.

The registry deliberately does **not** duplicate the prose descriptions or the
checklist's hand-authored pass criteria/status — those are human knowledge. It
owns the *structure* (the feature set + wiring) and keeps the prose honest.

Regenerate the catalog after editing this file::

    python -m game.retlab.features
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Feature:
    """One RetLab feature and its concrete wiring.

    ``key`` is a stable slug (never user-facing); ``title`` matches the CLAUDE.md
    "Features at a Glance" entry. ``doc_section`` is the §N in
    ``docs/dev/retlab-features.md`` (None for features documented only in design
    notes, e.g. the engine plugins). ``plugin_id`` is a ``resources/plugins/<id>``
    directory; ``settings_fields`` are ``Settings`` dataclass field names that gate
    the feature. ``retired`` marks a feature kept in the list as a tombstone.
    """

    key: str
    title: str
    doc_section: int | None = None
    plugin_id: str | None = None
    settings_fields: tuple[str, ...] = ()
    retired: bool = False


# THE registry. One entry per numbered "Features at a Glance" item (§1-30), plus
# the always-on engine plugins (no numbered section) at the end. Wiring fields are
# filled where a feature has a plugin and/or a Settings toggle; pure-behavior
# features carry none. The tests keep every reference honest and the set complete.
FEATURES: tuple[Feature, ...] = (
    Feature("qra_intercept_reserve", "QRA intercept reserve", 1, plugin_id="intercept"),
    Feature("jamming_c130j", "JAMMING flight type", 2, plugin_id="c130j"),
    Feature(
        "tarps_recon_fog",
        "Recon intel fog",
        3,
        settings_fields=(
            "recon_intel_fog",
            # Re-homed here 2026-08-07: this gate gutters through
            # TheaterGroundObject.hidden_on_player_map, a recon-fog leaf. It used to
            # hang off the §15 Sandy row, which went with the CSAR strip.
            "scar_command_post_intel",
        ),
    ),
    Feature("ui_transparency", "UI transparency", 4),
    Feature("target_location_precision", "Player target location precision", 5),
    Feature("air_defense_planning", "Air-defense planning rework", 6),
    Feature("auto_hide_mobile_sams", "Auto-hide mobile SAMs on MFD", 7),
    Feature("robustness_fixes", "Robustness / crash fixes", 8),
    Feature("tic", "TIC — Troops In Contact", 9, plugin_id="tic"),
    Feature("currenthill_iran_pack", "CurrentHill Iran assets pack", 10),
    Feature(
        "dtc_cartridge_export",
        "Native DCS DTC cartridge export",
        11,
        retired=True,
    ),
    Feature(
        "recon_engine",
        "Recon engine (TARPS + drone BDA)",
        12,
        retired=True,
    ),
    Feature("flight_control_atc", "Flight Control ATC", 13, retired=True),
    Feature("plugin_options_ui", "Plugin Options UI", 14),
    Feature(
        "scar_rescue",
        'SCAR — RESCAP "Sandy" rescue escort',
        15,
        retired=True,
    ),
    Feature("settings_qol_audit", "Settings QOL audit", 16),
    Feature(
        "planner_unpredictability",
        "Auto-planner target unpredictability",
        17,
        settings_fields=(
            "ownfor_planner_unpredictability",
            "opfor_planner_unpredictability",
        ),
    ),
    Feature("fog_overview_toggle", "Fog-of-war overview toggle", 18),
    Feature("map_layers_panel", "Unified map layers panel", 19),
    Feature(
        "drop_spawn_placement",
        "Drop-spawn: map right-click unit placement",
        20,
        retired=True,
    ),
    Feature(
        "combat_sar",
        "Combat SAR (fork implementation)",
        21,
        retired=True,
    ),
    Feature(
        "kneeboard_custom_import", "Kneeboard space-utilisation + custom import", 22
    ),
    Feature("per_squadron_country", "Per-squadron DCS country", 23),
    Feature(
        "date_gated_aircraft_properties",
        "Date-gated aircraft properties",
        24,
        settings_fields=("restrict_props_by_date",),
    ),
    Feature(
        "compact_kneeboard",
        "Compact 3-4 page kneeboard deck",
        25,
        retired=True,
    ),
    Feature("off_mission_combat", "Off-mission combat fidelity + PLAYER_AT_IP fix", 26),
    Feature("shared_airframe_kneeboard", "Shared-airframe kneeboard index", 27),
    Feature("settings_ia_reorg", "Settings IA reorg + difficulty presets", 28),
    Feature(
        "sitrep_kneeboard",
        "Campaign SITREP kneeboard band",
        29,
        settings_fields=("generate_sitrep_kneeboard",),
    ),
    Feature(
        "kneeboard_cover_page",
        "Dedicated kneeboard cover page",
        30,
        retired=True,
    ),
    Feature(
        "brief_sheet_kneeboard",
        "One-page Brief Sheet + deck-wide colour scheme",
        31,
        retired=True,
    ),
    Feature(
        "vietnam_arc_light",
        "Arc Light heavy-bomber Strike carpet",
        32,
        plugin_id="vietnamops",
        settings_fields=("vietnam_arc_light",),
    ),
    Feature(
        "vietnam_flak_gauntlet",
        "AAA flak gauntlet",
        33,
        plugin_id="vietnamops",
        settings_fields=("vietnam_flak_gauntlet",),
    ),
    Feature(
        "vietnam_naval_gunfire",
        "Naval gunfire support",
        34,
        plugin_id="vietnamops",
        settings_fields=("vietnam_naval_gunfire",),
    ),
    Feature(
        # Convoy interdiction is a force-model feature (a real, tracked enemy convoy created
        # in game/retlab/vietnam_convoy.py from finish_turn), not a vietnamops plugin
        # behaviour -- hence no plugin_id.
        "vietnam_convoy_interdiction",
        "Convoy interdiction (Steel Tiger)",
        35,
        settings_fields=("vietnam_convoy_interdiction",),
    ),
    Feature(
        # REMOVED 2026-09-16 (DM call). The barrage put DCS's airfield into its
        # under-attack state and every AI fixed-wing launch at that field was held
        # for the rest of the mission (tests 24, 31, 33, 34). The generic artillery
        # mode went with it. Tombstone only.
        "vietnam_airbase_harassment",
        "Airbase harassment (rocket/mortar siege)",
        36,
        retired=True,
    ),
    Feature(
        "vietnam_super_gaggle",
        "Super Gaggle hilltop resupply",
        37,
        plugin_id="vietnamops",
        settings_fields=("vietnam_super_gaggle",),
    ),
    Feature(
        "vietnam_fac_marking",
        "FAC(A) willie-pete target marking",
        38,
        plugin_id="vietnamops",
        settings_fields=("vietnam_fac_marking",),
    ),
    Feature(
        "vietnam_snake_and_nape",
        "Snake and nape (napalm CAS)",
        39,
        plugin_id="vietnamops",
        settings_fields=("vietnam_snake_and_nape",),
    ),
    Feature(
        "campaign_phases",
        "Campaign phases (inferred arc + planner emphasis)",
        40,
        retired=True,
    ),
    Feature(
        # Gated by the ModSettings/New Game `high_digit_sams` toggle (a wizard
        # field, not a Settings dataclass field) -- hence no settings_fields.
        "hds_ultimate_compilation",
        "High Digit SAMs Ultimate Compilation support",
        41,
    ),
    Feature(
        # No plugin, no Settings toggle: availability is on-disk content (a
        # tileset under Saved Games/Retribution/MapTiles, sliced by
        # tools/tile_geotiff.py and served by game/server/maptiles).
        "local_map_tiles",
        "Local DCS chart base layers (map tiles)",
        42,
    ),
    Feature(
        # No plugin, no Settings toggle: on-disk content is the switch (a JSON
        # store under Saved Games/Retribution, written from the payload tab by
        # game/retlab/flight_defaults.py, applied in Flight.__init__).
        "flight_defaults",
        "Per-aircraft flight defaults (save fuel + properties)",
        43,
    ),
    Feature(
        "long_range_carrier_ops",
        "Long-range carrier ops",
        44,
        settings_fields=("long_range_carrier_ops",),
    ),
    Feature(
        # No plugin, no Settings toggle: always-on like the other F10/ME map
        # drawings (frontlines/routes/CPs/ROE zones). Painted at generation by
        # game/missiongenerator/drawingsgenerator.py from the MissionData support
        # info; a toggle is a possible follow-up.
        "support_orbit_markers",
        "Support-package F10 orbit markers",
        45,
    ),
    Feature(
        # Reverted 2026-08-09 with the auto-planner re-convergence to upstream:
        # tanker tasking is upstream's again (every non-helo flight tanks when the
        # wing can plan REFUELING) and nothing fits tanks at plan or generation
        # time. Both gates were deleted; the external-fuel accounting helpers that
        # survived in game/retlab/range_fuel.py only feed fuel readouts.
        "auto_range_fuel_tanks",
        "Route-aware fuel-tank planning (fuel-first)",
        46,
        retired=True,
    ),
    Feature(
        "continuous_campaign_clock",
        "Continuous campaign clock & weather",
        47,
        settings_fields=("continuous_campaign_clock",),
    ),
    Feature(
        "vietnam_commitment_ceiling",
        "Commitment ceiling (will-coupled war budget)",
        48,
        retired=True,
    ),
    Feature(
        "mobile_missile_relocation",
        "Mobile missile relocation (the SCUD hunt)",
        49,
        retired=True,
    ),
    Feature(
        "convoy_ambush",
        "Convoy ambush (a chance, never telegraphed) + ambient supply convoys",
        50,
        # No plugin: the ambush spring is authored as native DCS trigger rules at
        # generation (game/missiongenerator/convoyambushgenerator.py).
        settings_fields=("convoy_ambush", "ambient_supply_convoys"),
    ),
    Feature(
        "enemy_comms_jamming",
        "Enemy comms jamming (IADS comms nodes)",
        51,
        retired=True,
    ),
    Feature(
        # Pure turn-model (no plugin): couples a side's command-network health to
        # its auto-planner unpredictability in game/retlab/c2_decapitation.py,
        # read at plan time through targetorder._unpredictability_for.
        "c2_decapitation",
        "Command-center decapitation degrades enemy planning",
        52,
        settings_fields=("c2_decapitation_effects",),
    ),
    Feature(
        "war_economy",
        "War economy",
        53,
        retired=True,
    ),
    Feature(
        "munitions_availability",
        "Munitions availability",
        54,
        retired=True,
    ),
    Feature(
        "red_intent",
        "Red Intent — adaptive enemy posture",
        55,
        retired=True,
    ),
    Feature(
        # Adopted from upstream PR dcs-retribution#859 (geofffranks). No plugin,
        # no Lua: a control point's not-deployed reserve armor is rendered as a
        # strikeable depot by MotorpoolPopulator + MotorpoolGenerator at mission
        # generation; each kill decrements base.armor 1:1
        # (game/sim/missionresultsprocessor.py commit_motorpool_losses), tracked
        # separately from front-line losses so a depot strike never shifts the
        # front. Inert until a campaign authors a Fortification.Garage_A depot.
        "motorpool_depots",
        "Strikeable motorpool depots",
        56,
        settings_fields=("motorpool_enabled", "motorpool_spawn_cap"),
    ),
    Feature(
        "air_droppable_minefields",
        "Air-droppable minefields",
        57,
        retired=True,
    ),
    Feature(
        # §58 mission-start briefing popup. Pure display: briefingluadata emits a
        # shared header (campaign/mission/date/time) + one record per player-crewed
        # flight (callsign/aircraft/task/field); the `briefing` plugin shows each
        # pilot their own card on S_EVENT_BIRTH (slot-in). No gameplay-model change.
        "mission_briefing_popup",
        "Mission-start briefing popup",
        58,
        plugin_id="briefing",
        settings_fields=("mission_briefing_popup",),
    ),
    Feature(
        # REMOVED 2026-09-23 (DM call). Never observed doing its job in a flown
        # test, and a sleeping group cannot be prosecuted by an AI strike or SEAD
        # flight (Desert Trident, 2026-08-24). Tombstone only.
        "ground_ai_sleep",
        "Ground AI sleep (graduated culling)",
        59,
        retired=True,
    ),
    Feature(
        # REMOVED 2026-09-29 (DM call). Every SAM site is back to one guidance
        # radar. Tombstone only.
        "sam_radar_redundancy",
        "SAM guidance-radar redundancy (two track radars per site)",
        60,
        retired=True,
    ),
    Feature(
        # §61 host red-interceptor scramble -- the game master's "give the boys
        # something to shoot" button (the M1 "it felt quiet after the first wave"
        # debrief). redscrambleluadata.py emits cold late-activation red fighter
        # clone templates (the QRA pattern, built in
        # AircraftGenerator.spawn_red_scramble_templates) + the red airfields
        # nearest-front first; the `redscramble` plugin builds a host-only F10
        # menu (per-player-name, or all-BLUE when unconfigured) that SPAWN-clones
        # a 2/4-ship at any listed base and GCI-vectors it onto the nearest
        # airborne blue fighters. Spawns are untracked event content by design
        # (the §20 drop-spawn cheat precedent).
        "host_red_scramble",
        "Host red-interceptor scramble (F10 bandit spawner)",
        61,
        plugin_id="redscramble",
        settings_fields=("host_red_scramble",),
    ),
    Feature(
        # pydcs deals random three-digit board numbers (an unordered set.pop);
        # ModexAllocator (game/missiongenerator/aircraft/modex.py) gives each
        # Hornet/Tomcat squadron a 100/200/300 block (Tomcats first, the CVW
        # convention) and numbers its jets sequentially X00, X01, ... in
        # generation order. Pure generation behavior — no setting, no plugin.
        # The Tomcat paints its board number into the livery instead, so
        # LiveryAllocator sequences those CAG-bird-first (2026-08-23).
        "squadron_modex",
        "Squadron-sequenced Hornet/Tomcat board numbers",
        62,
    ),
    Feature(
        # §63 ship-launched cruise missile raids: LACM warships (the Burke's
        # Tomahawks, the CurrentHill Kalibr hulls -- the curated LACM_SHIP_DCS_IDS
        # set) strike shore targets via a FireAtPoint task with the cruise-missile
        # weapon flag. game/retlab/cruise_raids.py owns the persisted per-group
        # magazines (debited only from the plugin's cruise_missiles_state debrief
        # report) + the one-raid-per-side-per-turn auto planner (C2-first target
        # pick, ROE-gated for BLUE); cruisemissileluadata.py emits ships + raids;
        # the `cruisemissiles` plugin fires the raids after a delay and serves the
        # per-coalition F10 call-for-fire menu. Real weapons from tracked ships --
        # kills record natively, point defense intercepts, no phantom spawns.
        "cruise_missile_raids",
        "Ship-launched cruise missile raids",
        63,
        plugin_id="cruisemissiles",
        settings_fields=("cruise_missile_strikes", "cruise_missile_auto_raids"),
    ),
    Feature(
        # §64 carrier deck spawn: AI carrier ground starts activate one second late so
        # DCS parks them clear of the six-pack (dcs_liberation#1309). Player flights
        # never do: in MP a late-activated client group is a "delayed start" slot
        # nobody can fly (test 54; the six-pack setting was removed 2026-10-07).
        # waypointgenerator.set_takeoff_time / needs_deck_placement_delay.
        "carrier_deck_policy",
        "Carrier deck spawn policy (AI off the six-pack + MP slot timing)",
        64,
    ),
    Feature(
        # §65 curated carrier comms: DCS auto-renders a "CV Operations Data"
        # kneeboard page straight from the miz, and the generator used to feed
        # it allocator junk (TACAN 1X + a random ident re-rolled every turn,
        # Link 4 on a random UHF, a fresh random ATC each mission, the boat
        # named "0796 | ..."). game/data/carrier_comms.py curates a per-hull
        # boat card (hull-number TACAN + boat ident, hull-keyed ICLS, Link 4
        # in the ACLS 336 MHz band, a stable ATC) applied with
        # stored-values-win / taken-channel-degrades-to-neighbor precedence in
        # GenericCarrierGenerator, which also names the flagship unit by its
        # hull name and persists every value so the card is stable across
        # turns. Pure generation behavior -- no setting, no plugin.
        "carrier_comms",
        "Curated carrier comms (CV Operations Data cleanup)",
        65,
    ),
    Feature(
        # §66 generated-mission archive: every turn generates to the one fixed
        # path retribution_nextturn.miz (the name the wiki/bug template/server
        # workflow all use), so each Take off overwrote the mission just flown --
        # and this fork root-causes its in-game findings from the flown miz.
        # game/retlab/mission_archive.py leaves that output alone and also
        # copies each generation to Missions/Retribution Archive/ under a
        # campaign_turnNN_stamp name (a folder DCS's mission browser lists).
        # Best-effort (never breaks Take off) and prunes only its own output.
        # Hooked in MissionSimulation.generate_miz. No setting -- a bounded ring
        # buffer, and a toggle would defeat the point (§42/§43 precedent).
        "mission_archive",
        "Generated-mission archive",
        66,
    ),
    Feature(
        # §67 weather-aware planning: the theater commander reads game.conditions
        # (game/retlab/weather_planning.py). Rain/storm suppresses the
        # automatic TARPS/drone recon add-on (PackageFulfiller); a thunderstorm
        # demotes the low-level visual-attack HTN methods (front-line CAS,
        # battle-position BAI, convoy interdiction) to the offensive tail
        # (PlanNextAction._offensive_order). Both coalitions -- same sky; clear
        # weather is byte-identical. Night is deliberately out: no per-airframe
        # night-capability data exists to gate on.
        "weather_aware_planning",
        "Weather-aware auto-planning",
        67,
        settings_fields=("weather_aware_planning",),
    ),
    Feature(
        # §68 adaptive procurement (game/retlab/adaptive_procurement.py):
        # the AI economy reads the war. Ground buys are price-weighted instead of
        # uniform random, and -- its own gate -- each side's commander repairs a
        # couple of destroyed SAM/EWR units per turn at surviving sites (full
        # price, degraded sites and radars first; C2/comms stay permanently dead),
        # so a rolled-back IADS stops being a one-way ratchet.
        "adaptive_procurement",
        "Adaptive procurement (price-weighted buys + SAM repair)",
        68,
        settings_fields=("adaptive_procurement", "auto_repair_air_defenses"),
    ),
    Feature(
        # §69 cross-package coordination (MissionScheduler._coordinate_sead_windows):
        # packages were timed independently, so a strike could arrive at a
        # defended target long before the SEAD tasked against the SAM covering
        # it. Movable AI strike/BAI/OCA packages whose target sits inside a
        # threat ring a SEAD/DEAD package is servicing are retimed into the
        # window just behind the latest covering suppressor -- SEAD opens, the
        # strikes push, several packages massing behind one window. Player
        # packages never move (a player SEAD still opens a window); the §8
        # carrier stagger runs after and only delays.
        "sead_strike_coordination",
        "Cross-package SEAD-before-strike coordination",
        69,
        # front_line_sead_escort: front-line CAS takes a SEAD escort, and the
        # Sidearm Harrier flies it instead of deep escorts (test 37).
        # route_around_sams: detour nav points round SAM rings off the target.
        settings_fields=(
            "sead_strike_coordination",
            "front_line_sead_escort",
            "route_around_sams",
            "tarcap_behind_sead",
        ),
    ),
    Feature(
        "comint_collection",
        "COMINT collection (blue-side communications intelligence)",
        70,
        retired=True,
    ),
    # §71 is gated by ModSettings.f4e_expanded_weapons (a Mods-page checkbox),
    # not a Settings field, so like the §10 asset pack it carries no wiring refs.
    Feature(
        "f4e_expanded_weapons_pack",
        "Expanded F-4E Weapons Pack (AGM-78/-88 Weasel fits)",
        71,
    ),
    Feature(
        # §72 deck dressing (game/data/carrier_deck_decor.py +
        # game/missiongenerator/carrierdeckdecor.py): ship-linked static deck
        # gear + LSO crew from campaign A replayed onto Nimitz-family
        # carriers, curated so every parking spawn spot, catapult and the
        # landing area stay usable; ten street variants rotate per turn (the
        # campaign A mining was completed 2026-08-07). One tier, standing all
        # mission -- the launch-phase round-down E-2C and the recovery-phase bow
        # respot were cut 2026-08-20, and the deckdecor plugin with them. No
        # static aircraft anywhere: late activations spawn INTO statics on spots
        # (flown 2026-07-18, and again at t+39 min in test 11).
        "carrier_deck_decorations",
        "Carrier deck decorations (campaign A deck dressing)",
        72,
        settings_fields=("carrier_deck_decorations",),
    ),
    Feature(
        # §73 default loadout per airframe+task (game/retlab/loadout_defaults.py):
        # one-click "set as default" writing the edited loadout into the payload
        # NAME the planner resolves for that task, so every future flight of the
        # airframe+task is planned with it. No Settings field -- on-disk content is
        # the switch, like the §42 map tiles and the §43 flight defaults.
        "default_task_loadout",
        "Per-airframe default loadout for a task",
        73,
    ),
    Feature(
        # §74 native DTC pre-population (game/missiongenerator/dtc/): one JSON
        # cartridge per blue client flight embedded at DTC/<name>.dtc in the miz
        # + the per-unit DTC.Cartridges/AutoLoad block, so the jet spawns with
        # steerpoints + push times, recovery TACAN/ICLS/ACLS, and
        # the SA/HSD picture (FLOT, CAP + tanker/AWACS orbits, viewer-fogged SAM
        # rings) already loaded -- zero pilot action, MP-distributed with the
        # mission download. The F-14B(U) takes the same seam with its own
        # sections. Supersedes the retired §11.
        "dtc_data_prepopulation",
        "Native DTC data pre-population (F/A-18C + F-16C + F-14B(U) + AH-64D)",
        74,
        settings_fields=("dtc_data_cartridges",),
    ),
    Feature(
        # §75 custom victory conditions: authored campaign `victory:` blocks
        # (victory CPs, domination, HVT destruction, category decapitation,
        # strength attrition, air denial) + two generic opt-in knobs, evaluated
        # in check_win_loss between the negotiation ending and the stock
        # capture-everything defaults. The knobs are the Settings wiring; the
        # authored tier needs none.
        "victory_conditions",
        "Custom victory conditions",
        75,
        settings_fields=(
            "alternate_victory_domination",
            "alternate_victory_attrition",
        ),
    ),
    Feature(
        # §76 CTLD paratroopers: fixed-wing troop transports (C-130J-30) fly
        # Air Assault by paradrop -- the planner admits any cabin_size > 0
        # airframe, and the ctld plugin's config layer jumps the stick (player:
        # airborne unload; AI: auto-release over the target zone). Rides the
        # ctld plugin toggle; no Settings field.
        "ctld_paratroopers",
        "CTLD paratroopers (fixed-wing air assault)",
        76,
        plugin_id="ctld",
    ),
    Feature(
        # §77 Escort jamming: the ESCORT_JAMMER escort role (auto-added on the
        # SEAD-escort radar-SAM trigger, rides the package join->split) + the
        # growler plugin's scripted EW effects -- a missile-spoof bubble over the
        # package and offensive ROE WEAPON_HOLD pulses on radar SAMs (emissions
        # never toggled). Flown only by dedicated jammers -- the EA-18G Growler and
        # EA-6B Prowler, the only airframes that declare the Escort Jammer task;
        # the plugin is airframe-agnostic so AI Growlers and Prowlers are driven
        # identically. Capped per side by max_escort_jammers. Rides the growler
        # plugin toggle.
        "growler_escort_jamming",
        "Escort jamming (Growler / Prowler)",
        77,
        plugin_id="growler",
        # single_sead_escort_flavour caps a package at one suppression flight so
        # the jammer's SEAD siblings stop crowding it out (in-game rows B52/B75).
        settings_fields=("max_escort_jammers", "single_sead_escort_flavour"),
    ),
    Feature(
        # §78 sea-supply convoys + coastal anti-ship engagement: a pure-engine feature
        # (no Lua). cargo_ship_convoys spreads a sea shipment across N hulls with
        # proportional losses (game/missiongenerator/cargoshipgenerator.py +
        # game/unitmap.py + the results processor); coastal_batteries_engage_ships sets
        # coastal batteries weapons-free so they fire on passing ships (tgogenerator.py).
        "sea_supply_convoys",
        "Sea-supply convoys + coastal anti-ship engagement",
        78,
        settings_fields=(
            "cargo_ship_convoys",
            "cargo_ship_convoy_max",
            "coastal_batteries_engage_ships",
        ),
    ),
    Feature(
        # Removed 2026-08-18 with the scout-to-reveal recon model: decoys only
        # worked because real field forces also hid behind circles, and they no
        # longer do.
        "decoy_zones",
        "Decoy suspected-activity zones",
        79,
        retired=True,
    ),
    Feature(
        # A layout slot generated one type of unit repeated N times, so every ship
        # group put to sea as four copies of one hull. NavalLayout.mix_unit_types
        # deals a type per slot around the lead hull, restricted to the lead's own
        # unit family (layout.UNIT_FAMILIES) and capped at MAX_MIXED_UNIT_TYPES, and
        # the carrier/LHA screens were widened to every surface combatant. Pure
        # generation behavior — no setting, no plugin.
        "mixed_hull_ship_groups",
        "Mixed-hull ship groups",
        80,
    ),
    Feature(
        # §81 cross-turn naval magazines: ships spawn ReturnFire and release to
        # weapons-free on a stagger (N1), and every anti-ship missile fired is
        # charged against a persisted per-group campaign stock that never rearms
        # (N2) -- so a fleet cannot dump its tubes in the opening minute of every
        # turn. game/retlab/naval_magazines.py + the navalmagazines plugin;
        # the weapon set is disjoint from §63's land-attack magazine.
        "naval_magazines",
        "Cross-turn naval magazines",
        81,
        plugin_id="navalmagazines",
        settings_fields=("naval_weapon_release_stagger", "naval_magazines"),
    ),
    Feature(
        "sp_pilot_mode",
        "SP Pilot Mode",
        83,
        settings_fields=("sp_pilot_mode",),
    ),
    Feature(
        # REMOVED 2026-08-16 on the DM's call -- "doesn't add much except in very
        # specific campaigns." The module, the `available_from_turn:`/`arrival_note:`
        # config fields, AirWing.pending_arrivals, the Sitrep arrivals band, the
        # briefing's anticipation section, both test files and the 8 authored
        # schedules are gone; only this tombstone keeps §82 resolvable.
        "wing_growth",
        "The Wing Grows",
        82,
        retired=True,
    ),
    Feature(
        # REMOVED 2026-08-06 after one flown look (WATCH item 1): the DM disliked
        # it and called a full rip. The module, both FlightMembers hooks, all four
        # settings, the 36 tests and WeaponGroup.category are gone; only this
        # tombstone remains so §84 stays a resolvable section number. Do not
        # restore -- see checklist B42 for the three guards a rebuild would owe.
        "stock_attrition",
        "Old-stock loadout attrition",
        84,
        retired=True,
    ),
    Feature(
        # §85 SAM battery support section -- the refuelling section and 5I57A
        # diesel power stations a real S-300 site carries. Pure unit-data +
        # layout-data (7 new resources/units/ground_units yamls, 3 new position
        # groups in the shared S-300_Site.miz, the S-300-family Logistics/Fuel/
        # Power slots, and the support units added to the 11 S-300-family preset
        # groups). No setting, no plugin, no save change. Also fixes two DEAD
        # slots -- layout slots naming a group that does not exist in the .miz
        # are silently dropped -- which had disabled the S-300 family's logistics
        # section and the Sky Sabre battery's point defence outright. CI-locked in
        # tests/armedforces/test_sam_support_vehicles.py.
        "sam_support_vehicles",
        "SAM battery support section (refuellers + power)",
        85,
    ),
    Feature(
        "gps_jamming",
        "GPS jamming (satellite-guided weapons go long)",
        86,
        plugin_id="gpsjamming",
        settings_fields=("gps_jamming",),
    ),
    Feature(
        # §87 naval station-keeping: a ship TGO with no campaign destination
        # generated with a zero-waypoint route and sat motionless on its marker all
        # mission, so every hull was a stationary target and a pre-planned
        # coordinate was always good. GroundObjectGenerator.hold_station gives it an
        # anchor-CENTRED racetrack (the mean position stays the campaign position,
        # so the map/threat rings/turn model stay honest) that DCS sails itself via
        # ordinary route waypoints + the ME's own SwitchWaypoint loop -- no plugin,
        # no Lua, nothing at runtime. Legs are water-sampled against the theater
        # landmap, and a group with no clear orientation keeps today's stationary
        # behaviour. Carrier/LHA control points are untouched (steam_into_wind).
        # Pure generation behavior -- no setting, no plugin, no save change.
        "naval_station_keeping",
        "Naval station-keeping racetracks",
        87,
    ),
    Feature(
        # §88 angled-deck recovery heading: steam_into_wind pointed the bow
        # straight into the wind, which puts the relative wind ~9 degrees off the
        # angled landing area on every real carrier, and computed carrier speed as
        # knots(25) - windspeed with no floor (negative above 25 kt of wind).
        # game/flightplan/carriercruisesolver.py solves heading + speed for ~25 kt
        # down the ANGLED deck with near-zero crosswind, and each carrier hull
        # carries its own landing_deck_angle in resources/units/ships. Adopted from
        # geofffranks' 12d71346 (upstream issue dcs-retribution#865).
        # Pure generation behavior -- no setting, no plugin, no save change.
        "carrier_angled_deck_recovery",
        "Angled-deck carrier recovery heading",
        88,
    ),
    Feature(
        "living_battlespace",
        "Living battlespace pre-roll",
        89,
        retired=True,
    ),
    Feature(
        # Seam 4 of the long-view note, rungs A-E. Five changes to how the ground
        # war moves: reinforcement gated on the supply route's kind, an assault
        # cost so taking ground is dearer than holding it, front placement that
        # counts the forces present, terrain that slows the advance, and a front
        # that bulges instead of running straight.
        # docs/dev/design/retlab-retribution-long-view.md.
        "front_line_ladder",
        "Front-line model: supply, assault cost, force weight, terrain, salients",
        90,
        settings_fields=(
            "supply_gated_reinforcement",
            "assault_costs_the_attacker",
            "scale_aware_front_line",
            "terrain_weighted_front_line",
            "front_line_salients",
        ),
    ),
    Feature(
        # Seam 1: one per-flight record of what the mission actually did, so the
        # campaign learns more than which units died. The general channel the
        # seven bespoke state.json extras should collapse into. Always on -- it
        # is the debrief schema, not an option.
        # docs/dev/design/retlab-retribution-long-view.md.
        "sortie_records",
        "Per-flight sortie records",
        91,
        plugin_id="base",
    ),
    Feature(
        # The recent-changes window on the toolbar. Reads resources/whatsnew/;
        # no plugin, no Settings gate -- it describes the build, not the campaign,
        # so it is available before a save is opened.
        "whats_new",
        "What's New",
        92,
    ),
    Feature(
        "region_priorities",
        "Region priorities",
        93,
        settings_fields=("region_priorities",),
    ),
    Feature(
        # Plugin-only: there is no Settings gate, because the plugin toggle IS the
        # gate and stock DCS behaviour is what you get with it off. Ported from
        # juanjux/dcs-retribution#63 at its post-perf-rewrite head, not the PR.
        "smart_threat_reaction",
        "Smart threat reaction",
        94,
        plugin_id="ai_reaction",
    ),
    Feature("pinned_bullseye", "Pinned bullseye", 95),
    Feature(
        # The career ledger between §91 (what a mission recorded) and the pilot
        # roster (who flew it). Ranks are data, not code:
        # resources/pilot_career.yaml.
        "pilot_career_logbook",
        "Pilot career logbook",
        96,
        settings_fields=("pilot_career_logbook",),
    ),
    Feature(
        # The career that outlives the campaign: same §91 records, second
        # destination, keyed by DCS player name and written outside every save.
        "lifetime_pilot_profiles",
        "Lifetime pilot profiles",
        97,
        settings_fields=("lifetime_pilot_profiles",),
    ),
    Feature(
        # §98 neutral-faction border defense: every nation on the map drawn with
        # its real border (tools/build_terrain_borders.py; shipped per terrain, no
        # campaign authoring needed). One with no coalition airfield inside it
        # stands a live SAM battery from mission start, neutral until a player
        # presses. Batteries are untracked event content (the §61 precedent); the
        # planner never learns the borders (no navmesh hazard — do not reopen the
        # §6 revert).
        "neutral_border_defense",
        "Neutral-faction border defense",
        98,
        plugin_id="neutralborder",
        settings_fields=("neutral_border_defense",),
    ),
    Feature(
        # The rescue escort. No settings field and no plugin: capability is the
        # aircraft yaml's Sandy task, and the role is hand-fragged only.
        "sandy_rescue_escort",
        "Sandy rescue escort",
        99,
    ),
    Feature(
        # The King's on-scene systems. Lives in the always-on opscsar plugin as
        # a second script, so no toggle of its own to forget.
        "king_on_scene",
        "King on-scene commander",
        100,
        plugin_id="opscsar",
    ),
    Feature(
        # Python only: the miz marks one client flight per base and type as
        # DCS's Dyn.SPAWN Template and writes the warehouse link. Gated on
        # dynamic_slots as well; off there means nothing is written.
        "dynamic_spawn_templates",
        "Dynamic spawn templates",
        101,
        settings_fields=("dynamic_slots_templates",),
    ),
    Feature("my_aircraft", "My aircraft and saved points", 102),
    Feature(
        # What losing each enemy target costs the enemy, ranked within its §93
        # family; a Target Intel line always, a blue-only planner weight when on.
        # docs/dev/design/retlab-hq-priority-targets-notes.md.
        "hq_priority_targets",
        "HQ priority targets",
        103,
        settings_fields=("hq_priority_targets",),
    ),
    Feature(
        # Always on, no setting (DM call 2026-09-23). FlightPlan.estimate_ground_ops
        # adds the wait behind earlier departures from the same field
        # (game/ato/runwayqueue.py); docs/dev/design/retlab-startup-times-notes.md.
        "runway_queue",
        "Runway queue at busy fields",
        104,
    ),
    Feature(
        # Gated by the ModSettings/New Game `iranairdefensepack` toggle (a wizard field,
        # not a Settings field). docs/dev/design/retlab-iran-air-defense-pack-notes.md
        # holds the contract.
        "iran_air_defense_pack",
        "RetLab Iran Air Defense Pack (3rd Khordad, Bavar-373)",
        105,
    ),
    Feature(
        # Always on. The package owns its join-to-IP and target-to-split NAV points
        # (game/ato/packageroute.py); docs/dev/design/retlab-package-route-notes.md.
        "package_route",
        "Package route",
        106,
    ),
    Feature(
        # Always on, no setting: a briefing.png/.jpg in Saved Games\DCS\Retribution
        # replaces the RetLab default (game/retlab/briefing_image.py).
        "briefing_image",
        "Briefing screen picture",
        107,
    ),
    Feature(
        # Always on, no setting: graded at results commit from §91's records
        # (game/retlab/flight_grades.py) and shown in the Qt debrief.
        "flight_report_cards",
        "Flight report cards",
        108,
    ),
    Feature(
        # Read-only REST API under /retribution-ai for an outside AI reviewing red's
        # turn (game/agent/); docs/dev/design/retlab-llm-opfor-notes.md.
        # outside_ai_plans_red is not listed: a listed boolean gate moves to the
        # RetLab Features page, and this one stays on HQ automation (DM call).
        "llm_opfor_reader",
        "Outside AI reads red's turn",
        109,
    ),
    # Always-on engine plugins — major RetLab machinery documented in design notes
    # rather than a numbered "Features at a Glance" entry.
    Feature("skynet_iads", "Skynet IADS engine", plugin_id="skynetiads"),
    Feature("splash_damage", "Splash Damage (RetLab tuned)", plugin_id="splashdamage3"),
)

# Path (relative to repo root) of the generated feature-catalog doc.
FEATURE_INDEX_DOC = "docs/dev/retlab-feature-index.md"


def _sorted_features() -> list[Feature]:
    """Numbered features by section ascending, then the unnumbered engines."""
    return sorted(
        FEATURES,
        key=lambda f: (f.doc_section is None, f.doc_section or 0),
    )


def render_feature_index() -> str:
    """Render :data:`FEATURES` to the Markdown catalog (a stable string)."""
    lines = [
        "# RetLab Feature Index",
        "",
        "> **Generated** from `game/retlab/features.py` — do not edit by hand.",
        "> Regenerate with `python -m game.retlab.features`; CI fails if stale.",
        "",
        'Every numbered feature in the CLAUDE.md "Features at a Glance" list (§N in',
        "[`retlab-features.md`](retlab-features.md)) is registered here, plus the",
        "always-on engine plugins. The wiring columns show the Lua plugin and",
        "`Settings` fields that run/gate each feature. A test (`tests/retlab/`)",
        "fails CI if a reference is stale, a numbered feature is missing, an in-game-",
        "pass checklist `§N` is unregistered, or this table drifts.",
        "",
        "| § | Feature | Plugin | Settings |",
        "| --- | --- | --- | --- |",
    ]
    for feature in _sorted_features():
        section = f"§{feature.doc_section}" if feature.doc_section is not None else "—"
        title = feature.title + (" _(retired)_" if feature.retired else "")
        plugin = f"`{feature.plugin_id}`" if feature.plugin_id else "—"
        if feature.settings_fields:
            settings = ", ".join(f"`{name}`" for name in feature.settings_fields)
        else:
            settings = "—"
        lines.append(f"| {section} | {title} | {plugin} | {settings} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    from pathlib import Path

    out = Path(FEATURE_INDEX_DOC)
    out.write_text(render_feature_index(), encoding="utf-8", newline="\n")
    print(f"wrote {out}")
