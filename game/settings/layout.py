"""How the Settings dialog lays out its fields: pages, sections, basic vs advanced."""

DIFFICULTY_PAGE = "Difficulty"

AI_DIFFICULTY_SECTION = "AI Difficulty"
MISSION_DIFFICULTY_SECTION = "Mission Difficulty"
MISSION_RESTRICTIONS_SECTION = "Mission Restrictions"

CAMPAIGN_MANAGEMENT_PAGE = "Campaign Management"

GENERAL_SECTION = "General"
PILOTS_AND_SQUADRONS_SECTION = "Pilots and Squadrons"
HQ_AUTOMATION_SECTION = "HQ Automation"
FLIGHT_PLANNER_AUTOMATION = "Flight Planner Automation"

CAMPAIGN_DOCTRINE_PAGE = "Campaign Doctrine"
DOCTRINE_DISTANCES_SECTION = "Doctrine distances"

MISSION_GENERATOR_PAGE = "Mission Generator"

GAMEPLAY_SECTION = "Gameplay"

KNEEBOARD_SECTION = "Kneeboard"

# TODO: Make sections a type and add headers.
# This section had the header: "Disabling settings below may improve performance, but
# will impact the overall quality of the experience."
PERFORMANCE_SECTION = "Performance"


# ---------------------------------------------------------------------------
# Settings UI information architecture (§28).
#
# The Settings dialog and the New Game wizard are both built entirely by walking
# Settings.pages() -> sections() -> fields(). Historically those followed raw
# field-declaration order, which scattered ~150 settings and left two 30+-item
# "General"/"Gameplay" grab-bag sections. `FIELD_LAYOUT` below is the single
# source of truth for how settings are grouped *and ordered* in the UI:
# field name -> (page, section). Page order = first appearance of a page here;
# section order = first appearance of a section within a page; field order =
# order here. Re-laying-out the UI is editing this table only — no field
# declaration moves, no behaviour change (field names/values/defaults are
# untouched). Any user field NOT listed here falls back to its own
# page=/section= metadata, so nothing is ever dropped.
#
# The legacy per-field page=/section= kwargs on the declarations are retained as
# that fallback; FIELD_LAYOUT overrides them for display.

# Pages (Campaign Management keeps its constant/label; Mission Generation's
# label now matches its existing icon key — see qt_ui/uiconstants.py).
DIFFICULTY_REALISM_PAGE = "Difficulty & Realism"
AIR_DOCTRINE_PAGE = "Air Doctrine"
MISSION_GENERATION_PAGE = "Mission Generation"
KNEEBOARDS_PAGE = "Kneeboards"
# Period-ops suite — Vietnam-era runtime mechanics, opt-in, default OFF globally and
# flipped ON by the Vietnam campaign YAMLs' settings: block. See
# docs/dev/design/retlab-vietnam-ops-notes.md.
VIETNAM_OPS_PAGE = "Vietnam Ops"
PERFORMANCE_PAGE = "Performance"

_LAYOUT_SPEC: list[tuple[str, list[tuple[str, list[str]]]]] = [
    (
        DIFFICULTY_REALISM_PAGE,
        [
            (
                "AI skill & economy",
                [
                    "player_skill",
                    "enemy_skill",
                    "enemy_vehicle_skill",
                    "player_income_multiplier",
                    "enemy_income_multiplier",
                ],
            ),
            (
                "Player aids",
                [
                    "invulnerable_player_pilots",
                    "external_views_allowed",
                    "easy_communication",
                    "battle_damage_assessment",
                    "labels",
                    "map_coalition_visibility",
                ],
            ),
            (
                "Realism & restrictions",
                [
                    "manpads",
                    "night_day_missions",
                    "restrict_weapons_by_date",
                    "restrict_props_by_date",
                    "target_intel_precision",
                    "recon_intel_fog",
                    "scar_command_post_intel",
                    "ai_unlimited_fuel",
                ],
            ),
            (
                "Combat search & rescue",
                [
                    "csar_enabled",
                    "csar_enabled_red",
                    "csar_ejection_chance",
                    "csar_control_point_radius",
                    "csar_cluster_radius",
                    "csar_survival_turns",
                    "csar_survival_turns_hostile",
                    "csar_ai_recovery_turns",
                    "csar_player_recovery_turns",
                ],
            ),
            (
                "CSAR flights",
                [
                    "max_csar_flights",
                    "csar_single_flight",
                    "csar_hover_extraction",
                    "csar_player_hover_height",
                    "csar_player_hover_distance",
                    "csar_rescue_ai_pilots",
                    "csar_require_open_doors",
                ],
            ),
            (
                "Attrition & replacements",
                [
                    "ai_pilot_levelling",
                    "enable_squadron_pilot_limits",
                    "squadron_pilot_limit",
                    "squadron_replenishment_rate",
                    "enable_squadron_aircraft_limits",
                ],
            ),
        ],
    ),
    (
        AIR_DOCTRINE_PAGE,
        [
            (
                "Air defense & QRA",
                [
                    "ownfor_default_qra_reserve",
                    "opfor_default_qra_reserve",
                    "qra_forward_defense",
                    "qra_comms_enabled",
                ],
            ),
            (
                "CAP & support timing",
                [
                    "desired_barcap_mission_duration",
                    "barcap_overlap_time",
                    "desired_awacs_mission_duration",
                    "desired_tanker_on_station_time",
                    "aircraft_per_recovery_tanker",
                ],
            ),
            (
                "Tanker autoplanning",
                [
                    "autoplan_tankers_for_strike",
                    "autoplan_tankers_for_oca",
                    "autoplan_tankers_for_dead",
                ],
            ),
            (
                "Auto-planner behavior",
                [
                    "oca_target_autoplanner_min_aircraft_count",
                    "ownfor_autoplanner_aggressiveness",
                    "opfor_autoplanner_aggressiveness",
                    "ownfor_planner_unpredictability",
                    "opfor_planner_unpredictability",
                    "region_priorities",
                    "hq_priority_targets",
                    "c2_decapitation_effects",
                    "weather_aware_planning",
                    "sead_strike_coordination",
                    "single_sead_escort_flavour",
                    "max_escort_jammers",
                ],
            ),
            (
                "Recon planning",
                [
                    "auto_add_tarps_recon",
                ],
            ),
            (
                "AI flight behavior",
                [
                    "atflir_autoswap",
                    "ai_jettison_empty_tanks",
                    "ai_vertical_takoff_landing",
                ],
            ),
            (
                "Altitudes",
                [
                    "heli_combat_alt_agl",
                    "heli_cruise_alt_agl",
                    "min_plane_altitude_offset",
                    "max_plane_altitude_offset",
                    "min_patrol_altitude",
                ],
            ),
            (
                "Engagement ranges",
                [
                    "airbase_threat_range",
                    "max_threat_range",
                    "cas_engagement_range_distance",
                    "armed_recon_engagement_range_distance",
                ],
            ),
            (
                "SEAD standoff",
                [
                    "sead_sweep_engagement_range_distance",
                    "sead_threat_buffer_min_distance",
                ],
            ),
            (
                "Support-orbit standoff",
                [
                    "tarcap_threat_buffer_min_distance",
                    "aewc_threat_buffer_min_distance",
                    "tanker_threat_buffer_min_distance",
                ],
            ),
            (
                "Mission range limits",
                [
                    "max_mission_range_planes",
                    "max_mission_range_helicopters",
                ],
            ),
        ],
    ),
    (
        CAMPAIGN_MANAGEMENT_PAGE,
        [
            (
                # The player-facing campaign features, together at the top of the
                # page (they used to be three one-field orphan sections).
                "Campaign features",
                [
                    "continuous_campaign_clock",
                    "long_range_carrier_ops",
                    "motorpool_enabled",
                    "sp_pilot_mode",
                    "pilot_career_logbook",
                    "lifetime_pilot_profiles",
                    "supply_gated_reinforcement",
                    "assault_costs_the_attacker",
                    "scale_aware_front_line",
                    "terrain_weighted_front_line",
                    "front_line_salients",
                ],
            ),
            (
                # §75 custom victory conditions: the two generic knobs (authored
                # campaign `victory:` blocks need no settings).
                "Victory conditions",
                [
                    "alternate_victory_domination",
                    "alternate_victory_attrition",
                ],
            ),
            (
                "Insurgency",
                [
                    "coin_insurgency",
                    "coin_reinfiltration",
                    "coin_ied",
                    "coin_hvt",
                    "coin_dispersed_cells",
                    "coin_harassment",
                ],
            ),
            (
                "HQ automation",
                [
                    "automate_runway_repair",
                    "automate_front_line_reinforcements",
                    "automate_aircraft_reinforcements",
                    "auto_ato_behavior",
                    "auto_ato_behavior_awacs",
                    "auto_ato_behavior_tankers",
                    "auto_ato_player_missions_asap",
                    "outside_ai_plans_red",
                    "automate_front_line_stance",
                    "default_front_line_stance",
                ],
            ),
            (
                "Commander economy",
                [
                    "adaptive_procurement",
                    "auto_repair_air_defenses",
                    "auto_procurement_balance",
                    "frontline_reserves_factor",
                    "reserves_procurement_target",
                    "auto_procurement_balance_red",
                    "frontline_reserves_factor_red",
                    "reserves_procurement_target_red",
                ],
            ),
            (
                "Flight-planner automation",
                [
                    "fpa_2ship_weight",
                    "fpa_3ship_weight",
                    "fpa_4ship_weight",
                    "primary_task_distance_factor",
                ],
            ),
            (
                "Squadrons & loadouts",
                [
                    "squadron_random_chance",
                    "apply_target_overrides_to_loadouts",
                ],
            ),
        ],
    ),
    (
        MISSION_GENERATION_PAGE,
        [
            (
                "Simulation & fast-forward",
                [
                    "fast_forward_stop_condition",
                    "combat_resolution_method",
                    "never_delay_player_flights",
                    "use_ai_combat_landing",
                    "desired_player_mission_duration",
                ],
            ),
            (
                "Aircraft start types",
                [
                    "default_start_type",
                    "default_start_type_client",
                    "opfor_air_start",
                    "support_air_start",
                    "csar_start_type",
                ],
            ),
            (
                "Player slots",
                [
                    "dynamic_slots",
                    "dynamic_slots_hot",
                    "dynamic_slots_templates",
                    "dynamic_cargo",
                    "untasked_opfor_client_slots",
                    "game_masters_count",
                    "tactical_commander_count",
                    "jtac_count",
                    "observer_count",
                    "player_startup_time",
                ],
            ),
            (
                "Cockpit & nav aids",
                [
                    "generate_portable_tacans",
                    "generate_marks",
                    "datalink_policy",
                    "default_player_laser_code",
                    "switch_baro_fix",
                    "ai_radio_behavior",
                ],
            ),
            (
                "Ground start",
                [
                    "ground_start_ai_planes",
                    "ground_start_scenery_remove_triggers",
                    "ground_start_trucks",
                    "ground_start_ground_power_trucks",
                    "ground_start_airbase_statics_farps_remove",
                ],
            ),
            (
                "Carrier",
                [
                    "supercarrier",
                    "supercarrier_deck_crew",
                    "carrier_deck_decorations",
                ],
            ),
            (
                "Weather",
                [
                    "cloud_preset_pack",
                    "atmosx_live_weather",
                    "atmosx_cli_path",
                    "atmosx_metar_station",
                ],
            ),
            (
                "World & systems",
                [
                    "max_frontline_width",
                    "use_auto_fog",
                ],
            ),
            (
                # In-mission life on the ground: cosmetic siege damage, traffic
                # and the convoy war.
                "Battlefield life",
                [
                    "base_battle_damage",
                    "civilian_air_traffic",
                    "ambient_supply_convoys",
                    "convoy_ambush",
                    "mission_briefing_popup",
                    "neutral_border_defense",
                ],
            ),
            (
                # Native DCS data cartridges (§74): the jet starts with the
                # mission already in the avionics.
                "Cockpit data",
                [
                    "dtc_data_cartridges",
                ],
            ),
            (
                # Ship-launched land-attack fires (§63) -- the finite-magazine
                # cruise missile game, kept out of the (full) Battlefield life
                # grab of in-mission texture toggles.
                "Naval strike",
                [
                    "cruise_missile_strikes",
                    "cruise_missile_auto_raids",
                    "cargo_ship_convoys",
                    "coastal_batteries_engage_ships",
                    "naval_weapon_release_stagger",
                    "naval_magazines",
                ],
            ),
            (
                "Sea supply convoys",
                [
                    "cargo_ship_convoy_max",
                ],
            ),
            (
                # Game-master levers for hosted multiplayer events -- deliberate
                # host actions, never automatic systems.
                "Host & event tools",
                [
                    "host_red_scramble",
                ],
            ),
        ],
    ),
    (
        KNEEBOARDS_PAGE,
        [
            (
                "Kneeboards",
                [
                    "generate_dark_kneeboard",
                    "generate_target_recon_kneeboard",
                    "generate_all_packages_kneeboard",
                    "generate_threat_intel_kneeboard",
                    "enable_package_code_words",
                    "generate_sitrep_kneeboard",
                ],
            ),
        ],
    ),
    (
        VIETNAM_OPS_PAGE,
        [
            (
                "Fire support",
                [
                    "vietnam_arc_light",
                    "vietnam_naval_gunfire",
                    "vietnam_snake_and_nape",
                ],
            ),
            (
                "Battlefield & interdiction",
                [
                    "vietnam_flak_gauntlet",
                    "vietnam_convoy_interdiction",
                    "vietnam_super_gaggle",
                    "vietnam_fac_marking",
                ],
            ),
        ],
    ),
    (
        PERFORMANCE_PAGE,
        [
            (
                "World detail",
                [
                    "perf_smoke_gen",
                    "perf_smoke_spacing",
                    "perf_artillery",
                    "generate_fire_tasks_for_missile_sites",
                    "perf_moving_units",
                    "convoys_travel_full_distance",
                    "perf_disable_convoys",
                    "perf_disable_cargo_ships",
                    "perf_frontline_units_prefer_roads",
                    "perf_frontline_units_max_supply",
                    "motorpool_spawn_cap",
                    "perf_infantry",
                    "perf_destroyed_units",
                ],
            ),
            (
                "Culling & untasked units",
                [
                    "perf_disable_untasked_blufor_aircraft",
                    "perf_disable_untasked_opfor_aircraft",
                    "perf_culling",
                    "perf_culling_distance",
                    "perf_do_not_cull_threatening_iads",
                    "perf_do_not_cull_carrier",
                    "perf_ai_despawn_airstarted",
                ],
            ),
        ],
    ),
]

# The RetLab Features page (§28). The split is the mental model: this page answers
# "what is running", the topical pages answer "how it behaves", so a feature's
# on/off switch lives here and its tuning knobs stay beside what they tune.
#
# FEATURE_GATE_FIELDS is a literal rather than an import of the feature registry
# because game/__init__ already pulls in this module -- importing the registry
# would be circular. tests/retlab/test_features_registry.py fails CI if the
# two fall out of step.
FEATURES_PAGE = "RetLab Features"

FEATURE_GATE_FIELDS: dict[str, list[str]] = {
    "Recon, concealment & intel": [
        "recon_intel_fog",  # §3
        "scar_command_post_intel",  # §3 (re-homed from the retired §15 row)
    ],
    "Battlefield life": [
        "ambient_supply_convoys",  # §50
        "convoy_ambush",  # §50
        "motorpool_enabled",  # §56
        "mission_briefing_popup",  # §58
        "neutral_border_defense",  # §98
    ],
    "Electronic & command warfare": [
        "c2_decapitation_effects",  # §52
        "gps_jamming",  # §86
    ],
    "Naval & missile strike": [
        "long_range_carrier_ops",  # §44
        "cruise_missile_strikes",  # §63
        "cruise_missile_auto_raids",  # §63
        "cargo_ship_convoys",  # §78
        "coastal_batteries_engage_ships",  # §78
        "naval_weapon_release_stagger",  # §81
        "naval_magazines",  # §81
    ],
    "Auto-planner behavior": [
        "region_priorities",  # §93
        "hq_priority_targets",  # §103
        "weather_aware_planning",  # §67
        "sead_strike_coordination",  # §69
        "single_sead_escort_flavour",  # §77
        "front_line_sead_escort",  # §69
        "route_around_sams",  # §69
        "tarcap_behind_sead",  # §69
        "adaptive_procurement",  # §68
        "auto_repair_air_defenses",  # §68
    ],
    "Pilots & careers": [
        "pilot_career_logbook",  # §96
        "lifetime_pilot_profiles",  # §97
    ],
    "Single-player flow": [
        "sp_pilot_mode",  # §83
        # §89's boolean gates only -- the pre-roll ceiling is an int knob, and
        # the Features page contract is boolean gates (test_settings_filter);
        # the cap stays in Campaign Management -> Campaign features.
    ],
    "Ground war": [
        "supply_gated_reinforcement",  # §90 rung A
        "assault_costs_the_attacker",  # §90 rung B
        "scale_aware_front_line",  # §90 rung C
        "terrain_weighted_front_line",  # §90 rung D
        "front_line_salients",  # §90 rung E
    ],
    "Campaign clock & era": [
        "continuous_campaign_clock",  # §47
        "restrict_props_by_date",  # §24
    ],
    "Cockpit & kneeboard": [
        "dtc_data_cartridges",  # §74
        "generate_sitrep_kneeboard",  # §29
    ],
    "Carrier": [
        "carrier_deck_decorations",  # §72
    ],
    "Host & event tools": [
        "host_red_scramble",  # §61
        "dynamic_slots_templates",  # §101
    ],
}

#: Flat set of every field the Features page claims, for the layout rebuild below.
_FEATURE_GATE_NAMES: frozenset[str] = frozenset(
    name for names in FEATURE_GATE_FIELDS.values() for name in names
)

# The spec with the feature gates lifted out of their old topical sections, then
# the Features page appended. A section left empty by the lift is dropped rather
# than rendering as an empty group box.
_LAYOUT_SPEC_WITHOUT_GATES: list[tuple[str, list[tuple[str, list[str]]]]] = [
    (
        page,
        [
            (section, kept)
            for section, names in sections
            if (kept := [n for n in names if n not in _FEATURE_GATE_NAMES])
        ],
    )
    for page, sections in _LAYOUT_SPEC
]

_EFFECTIVE_LAYOUT_SPEC: list[tuple[str, list[tuple[str, list[str]]]]] = [
    *_LAYOUT_SPEC_WITHOUT_GATES,
    (
        FEATURES_PAGE,
        [(section, names) for section, names in FEATURE_GATE_FIELDS.items()],
    ),
]

# Flattened field -> (page, section). Insertion order (and thus UI order) is the
# spec order above.
FIELD_LAYOUT: dict[str, tuple[str, str]] = {
    name: (page, section)
    for page, sections in _EFFECTIVE_LAYOUT_SPEC
    for section, names in sections
    for name in names
}

# No settings field is hidden from the UI today. §57's two minefield toggles were the
# only members and went with the feature on 2026-09-07; the set is kept because the
# dialog and the New Game wizard both consult it.
HIDDEN_FIELDS: frozenset[str] = frozenset()

# ---------------------------------------------------------------------------
# Basic vs advanced.
#
# The dialog shows a section's basic options and folds the rest behind a "Show N
# advanced options" link. The rule is deliberately mechanical rather than 213
# hand-made judgment calls, so it can be read and argued with in one sitting:
#
#     advanced  ==  a numeric tuning knob (int / float / duration)
#
# A number answers "how much" about a behaviour you have already chosen, which is
# the definition of a knob you reach for second. Booleans and choices stay basic:
# they answer "which" or "whether", and those are the decisions that shape a
# campaign.
#
# Two exceptions to the rule, both explicit below: numbers that ARE the decision
# (the difficulty economy/skill dials the preset bar drives, so the preset and the
# page can never disagree about what matters), and a short list of expert booleans
# that fail the spirit of the rule.
#
# `advanced=True` on an individual declaration also works and wins; prefer it for
# a new field whose home is obvious, and this table for bulk classification.
_PRESET_DRIVEN_FIELDS: frozenset[str] = frozenset(
    {
        "player_income_multiplier",
        "enemy_income_multiplier",
    }
)

_ALWAYS_BASIC_FIELDS: frozenset[str] = frozenset(
    {
        # Squadron/airframe scale reads as a headline campaign choice, not a knob.
        "default_start_type",
    }
)

#: Expert booleans/choices that the "numbers are advanced" rule alone would leave
#: in front of every player. These are debugging and test aids, not gameplay.
_ADVANCED_NON_NUMERIC_FIELDS: frozenset[str] = frozenset(
    {
        "switch_baro_fix",
        "ground_start_scenery_remove_triggers",
    }
)

#: ``Settings.__dict__`` key holding the field names a campaign pre-seeded. Not a
#: dataclass field on purpose -- see Settings.campaign_preseeded_fields.
CAMPAIGN_PRESEED_KEY = "_campaign_preseeded_fields"
