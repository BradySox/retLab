# RetLab Feature Index

> **Generated** from `game/retlab/features.py` — do not edit by hand.
> Regenerate with `python -m game.retlab.features`; CI fails if stale.

Every numbered feature in the CLAUDE.md "Features at a Glance" list (§N in
[`retlab-features.md`](retlab-features.md)) is registered here, plus the
always-on engine plugins. The wiring columns show the Lua plugin and
`Settings` fields that run/gate each feature. A test (`tests/retlab/`)
fails CI if a reference is stale, a numbered feature is missing, an in-game-
pass checklist `§N` is unregistered, or this table drifts.

| § | Feature | Plugin | Settings |
| --- | --- | --- | --- |
| §1 | QRA intercept reserve | `intercept` | — |
| §2 | JAMMING flight type | `c130j` | — |
| §3 | Recon intel fog | — | `recon_intel_fog`, `scar_command_post_intel` |
| §4 | UI transparency | — | — |
| §5 | Player target location precision | — | — |
| §6 | Air-defense planning rework | — | — |
| §7 | Auto-hide mobile SAMs on MFD | — | — |
| §8 | Robustness / crash fixes | — | — |
| §9 | TIC — Troops In Contact | `tic` | — |
| §10 | CurrentHill Iran assets pack | — | — |
| §11 | Native DCS DTC cartridge export _(retired)_ | — | — |
| §12 | Recon engine (TARPS + drone BDA) _(retired)_ | — | — |
| §13 | Flight Control ATC _(retired)_ | — | — |
| §14 | Plugin Options UI | — | — |
| §15 | SCAR — RESCAP "Sandy" rescue escort _(retired)_ | — | — |
| §16 | Settings QOL audit | — | — |
| §17 | Auto-planner target unpredictability | — | `ownfor_planner_unpredictability`, `opfor_planner_unpredictability` |
| §18 | Fog-of-war overview toggle | — | — |
| §19 | Unified map layers panel | — | — |
| §20 | Drop-spawn: map right-click unit placement _(retired)_ | — | — |
| §21 | Combat SAR (fork implementation) _(retired)_ | — | — |
| §22 | Kneeboard space-utilisation + custom import | — | — |
| §23 | Per-squadron DCS country | — | — |
| §24 | Date-gated aircraft properties | — | `restrict_props_by_date` |
| §25 | Compact 3-4 page kneeboard deck _(retired)_ | — | — |
| §26 | Off-mission combat fidelity + PLAYER_AT_IP fix | — | — |
| §27 | Shared-airframe kneeboard index | — | — |
| §28 | Settings IA reorg + difficulty presets | — | — |
| §29 | Campaign SITREP kneeboard band | — | `generate_sitrep_kneeboard` |
| §30 | Dedicated kneeboard cover page _(retired)_ | — | — |
| §31 | One-page Brief Sheet + deck-wide colour scheme _(retired)_ | — | — |
| §32 | Arc Light heavy-bomber Strike carpet | `vietnamops` | `vietnam_arc_light` |
| §33 | AAA flak gauntlet | `vietnamops` | `vietnam_flak_gauntlet` |
| §34 | Naval gunfire support | `vietnamops` | `vietnam_naval_gunfire` |
| §35 | Convoy interdiction (Steel Tiger) | — | `vietnam_convoy_interdiction` |
| §36 | Airbase harassment (rocket/mortar siege) _(retired)_ | — | — |
| §37 | Super Gaggle hilltop resupply | `vietnamops` | `vietnam_super_gaggle` |
| §38 | FAC(A) willie-pete target marking | `vietnamops` | `vietnam_fac_marking` |
| §39 | Snake and nape (napalm CAS) | `vietnamops` | `vietnam_snake_and_nape` |
| §40 | Campaign phases (inferred arc + planner emphasis) _(retired)_ | — | — |
| §41 | High Digit SAMs Ultimate Compilation support | — | — |
| §42 | Local DCS chart base layers (map tiles) | — | — |
| §43 | Per-aircraft flight defaults (save fuel + properties) | — | — |
| §44 | Long-range carrier ops | — | `long_range_carrier_ops` |
| §45 | Support-package F10 orbit markers | — | — |
| §46 | Route-aware fuel-tank planning (fuel-first) _(retired)_ | — | — |
| §47 | Continuous campaign clock & weather | — | `continuous_campaign_clock` |
| §48 | Commitment ceiling (will-coupled war budget) _(retired)_ | — | — |
| §49 | Mobile missile relocation (the SCUD hunt) _(retired)_ | — | — |
| §50 | Convoy ambush (a chance, never telegraphed) + ambient supply convoys | — | `convoy_ambush`, `ambient_supply_convoys` |
| §51 | Enemy comms jamming (IADS comms nodes) _(retired)_ | — | — |
| §52 | Command-center decapitation degrades enemy planning | — | `c2_decapitation_effects` |
| §53 | War economy _(retired)_ | — | — |
| §54 | Munitions availability _(retired)_ | — | — |
| §55 | Red Intent — adaptive enemy posture _(retired)_ | — | — |
| §56 | Strikeable motorpool depots | — | `motorpool_enabled`, `motorpool_spawn_cap` |
| §57 | Air-droppable minefields _(retired)_ | — | — |
| §58 | Mission-start briefing popup | `briefing` | `mission_briefing_popup` |
| §59 | Ground AI sleep (graduated culling) _(retired)_ | — | — |
| §60 | SAM guidance-radar redundancy (two track radars per site) _(retired)_ | — | — |
| §61 | Host red-interceptor scramble (F10 bandit spawner) | `redscramble` | `host_red_scramble` |
| §62 | Squadron-sequenced Hornet/Tomcat board numbers | — | — |
| §63 | Ship-launched cruise missile raids | `cruisemissiles` | `cruise_missile_strikes`, `cruise_missile_auto_raids` |
| §64 | Carrier deck spawn policy (AI off the six-pack + MP slot timing) | — | — |
| §65 | Curated carrier comms (CV Operations Data cleanup) | — | — |
| §66 | Generated-mission archive | — | — |
| §67 | Weather-aware auto-planning | — | `weather_aware_planning` |
| §68 | Adaptive procurement (price-weighted buys + SAM repair) | — | `adaptive_procurement`, `auto_repair_air_defenses` |
| §69 | Cross-package SEAD-before-strike coordination | — | `sead_strike_coordination`, `front_line_sead_escort`, `route_around_sams`, `tarcap_behind_sead` |
| §70 | COMINT collection (blue-side communications intelligence) _(retired)_ | — | — |
| §71 | Expanded F-4E Weapons Pack (AGM-78/-88 Weasel fits) | — | — |
| §72 | Carrier deck decorations (campaign A deck dressing) | — | `carrier_deck_decorations` |
| §73 | Per-airframe default loadout for a task | — | — |
| §74 | Native DTC data pre-population (F/A-18C + F-16C + F-14B(U) + AH-64D) | — | `dtc_data_cartridges` |
| §75 | Custom victory conditions | — | `alternate_victory_domination`, `alternate_victory_attrition` |
| §76 | CTLD paratroopers (fixed-wing air assault) | `ctld` | — |
| §77 | Escort jamming (Growler / Prowler) | `growler` | `max_escort_jammers`, `single_sead_escort_flavour` |
| §78 | Sea-supply convoys + coastal anti-ship engagement | — | `cargo_ship_convoys`, `cargo_ship_convoy_max`, `coastal_batteries_engage_ships` |
| §79 | Decoy suspected-activity zones _(retired)_ | — | — |
| §80 | Mixed-hull ship groups | — | — |
| §81 | Cross-turn naval magazines | `navalmagazines` | `naval_weapon_release_stagger`, `naval_magazines` |
| §82 | The Wing Grows _(retired)_ | — | — |
| §83 | SP Pilot Mode | — | `sp_pilot_mode` |
| §84 | Old-stock loadout attrition _(retired)_ | — | — |
| §85 | SAM battery support section (refuellers + power) | — | — |
| §86 | GPS jamming (satellite-guided weapons go long) | `gpsjamming` | `gps_jamming` |
| §87 | Naval station-keeping racetracks | — | — |
| §88 | Angled-deck carrier recovery heading | — | — |
| §89 | Living battlespace pre-roll _(retired)_ | — | — |
| §90 | Front-line model: supply, assault cost, force weight, terrain, salients | — | `supply_gated_reinforcement`, `assault_costs_the_attacker`, `scale_aware_front_line`, `terrain_weighted_front_line`, `front_line_salients` |
| §91 | Per-flight sortie records | `base` | — |
| §92 | What's New | — | — |
| §93 | Region priorities | — | `region_priorities` |
| §94 | Smart threat reaction | `ai_reaction` | — |
| §95 | Pinned bullseye | — | — |
| §96 | Pilot career logbook | — | `pilot_career_logbook` |
| §97 | Lifetime pilot profiles | — | `lifetime_pilot_profiles` |
| §98 | Neutral-faction border defense | `neutralborder` | `neutral_border_defense` |
| §99 | Sandy rescue escort | — | — |
| §100 | King on-scene commander | `opscsar` | — |
| §101 | Dynamic spawn templates | — | `dynamic_slots_templates` |
| §102 | My aircraft and saved points | — | — |
| §103 | HQ priority targets | — | `hq_priority_targets` |
| §104 | Runway queue at busy fields | — | — |
| §105 | RetLab Iran Air Defense Pack (3rd Khordad, Bavar-373) | — | — |
| §106 | Package route | — | — |
| §107 | Briefing screen picture | — | — |
| §108 | Flight report cards | — | — |
| §109 | Outside AI reads red's turn | — | — |
| — | Skynet IADS engine | `skynetiads` | — |
| — | Splash Damage (RetLab tuned) | `splashdamage3` | — |
