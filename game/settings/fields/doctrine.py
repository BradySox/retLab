"""Campaign doctrine: QRA, CAP, tanker and planner distances."""

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING


from ..booleanoption import boolean_option
from ..boundedintoption import bounded_int_option
from ..minutesoption import minutes_option

if TYPE_CHECKING:
    pass
from ..layout import CAMPAIGN_DOCTRINE_PAGE, DOCTRINE_DISTANCES_SECTION, GENERAL_SECTION


@dataclass
class DoctrineSettings:
    # CAMPAIGN DOCTRINE
    desired_barcap_mission_duration: timedelta = minutes_option(
        "Desired BARCAP on-station time",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        default=timedelta(minutes=60),
        min=30,
        max=150,
        detail=(
            "Also determines how many BARCAP waves are planned: mission duration "
            "divided by the FRESH coverage each wave adds, which is this value "
            "minus BARCAP wave overlap. A carrier plans double that number, and "
            "flies them in stacks of Max simultaneous carrier BARCAP waves."
        ),
    )
    barcap_overlap_time: timedelta = minutes_option(
        "BARCAP wave overlap",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        # Stock default (2026-08-09 re-convergence): upstream schedules
        # back-to-back waves. RetLab planner suite preset sets 15.
        default=timedelta(minutes=0),
        min=0,
        max=60,
        detail="How long consecutive BARCAP waves overlap on-station. Higher values"
        " plan more, more-frequent waves so coverage has no handoff gap. 0 restores"
        " back-to-back, non-overlapping waves (the legacy behavior).",
    )
    ownfor_default_qra_reserve: int = bounded_int_option(
        "Default QRA reserve per OWNFOR interceptor squadron",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        default=0,
        min=0,
        max=12,
        detail=(
            "At new-game start, seeds this many QRA (hot-alert intercept) aircraft "
            "for each BARCAP-capable OWNFOR squadron. Per-squadron values can be "
            "edited afterward and are saved with the campaign."
        ),
    )
    opfor_default_qra_reserve: int = bounded_int_option(
        "Default QRA reserve per OPFOR interceptor squadron",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        default=0,
        min=0,
        max=12,
        detail=(
            "At new-game start, seeds this many QRA (hot-alert intercept) aircraft "
            "for each BARCAP-capable OPFOR squadron. Lets OPFOR lean on interception "
            "independently of OWNFOR. Per-squadron values can be edited afterward."
        ),
    )
    qra_forward_defense: bool = boolean_option(
        "QRA defends the front (rear bases answer forward raids)",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        default=True,
        detail=(
            "Alert fighters at rear bases scramble to fight over the front line "
            "instead of only answering raids near their own runway. Each side is "
            "confined to the airspace over its own bases and its own side of the "
            "front, so defenders never chase deep into enemy territory. The closest "
            "base still answers first; a rear base only launches once the closer "
            "one's alert aircraft are spent. Turn this off for the legacy behavior, "
            "where a base only ever defends itself."
        ),
    )
    qra_comms_enabled: bool = boolean_option(
        "QRA radio scramble callouts",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        default=True,
        detail=(
            "Enables the dispatcher's defender-POV radio/text callouts (scramble, "
            "wheels up, engaging, RTB) on the coalition F10 menu and radio TTS."
        ),
    )
    desired_awacs_mission_duration: timedelta = minutes_option(
        "Desired AWACS on-station time",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        default=timedelta(minutes=120),
        min=60,
        max=300,
        detail=(
            "Also determines how many AWACS flights are planned: mission duration "
            "divided by desired on-station time."
        ),
    )
    desired_tanker_on_station_time: timedelta = minutes_option(
        "Desired tanker on-station time",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        default=timedelta(minutes=60),
        min=30,
        max=300,
        detail=(
            "Also determines how many tanker flights are planned: mission duration "
            "divided by desired on-station time."
        ),
    )
    autoplan_tankers_for_strike: bool = boolean_option(
        "Auto-planner plans refueling flights for Strike packages",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        default=True,
        invert=False,
        detail=(
            "If checked, the auto-planner will include tankers in Strike packages, "
            "provided the faction has access to them."
        ),
    )
    autoplan_tankers_for_oca: bool = boolean_option(
        "Auto-planner plans refueling flights for OCA packages",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        default=True,
        invert=False,
        detail=(
            "If checked, the auto-planner will include tankers in OCA packages, "
            "provided the faction has access to them."
        ),
    )
    autoplan_tankers_for_dead: bool = boolean_option(
        "Auto-planner plans refueling flights for DEAD packages",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        default=True,
        invert=False,
        detail=(
            "If checked, the auto-planner will include tankers in DEAD packages, "
            "provided the faction has access to them."
        ),
    )
    auto_add_tarps_recon: bool = boolean_option(
        "Auto-planner adds a recon flight to Strike/DEAD/Armed Recon packages",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        # Stock default (2026-08-09 re-convergence): upstream plans no add-on
        # recon. RetLab planner suite preset turns this on.
        default=False,
        invert=False,
        detail=(
            "If checked, the auto-planner appends a single photo-recon flight "
            "(e.g. F-14 TARPS, or a Predator/Reaper drone on a UAV-fielding "
            "faction) to Strike and DEAD packages against high-value targets "
            "(air defenses, factories, command posts, bridges) and to Armed Recon "
            "packages. What it brings back is a hidden enemy command post within "
            "3 NM of the package's target, revealed on your map; engaging a site "
            "is what reveals everything else. Requires a TARPS-capable squadron "
            "in range; if none is available the flight is simply skipped (the "
            "package is never scrubbed)."
        ),
    )
    recon_intel_fog: bool = boolean_option(
        "Recon intel fog (hide enemy site composition until engaged)",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        default=True,
        invert=False,
        detail=(
            "When enabled, enemy ground sites appear on the map as targets you can "
            "plan against, but what is actually there — unit types, counts, and "
            "threat/detection rings — stays hidden until you engage the site: put "
            "ordnance on it, or send any ground-attack sortie that reaches it. "
            "Recon overflight does not reveal. Fixed SAM sites (SA-2, SA-3, SA-5, SA-10/20, S-400, Patriot and Hawk) are always "
            "known. Once a site is engaged you see it "
            "in full and permanently, damage included — there is no separate BDA "
            "confirmation step. The AI planner and threat math always use full "
            "truth, so auto-planning is unaffected. Existing campaigns keep "
            "everything revealed; the fog applies to new campaigns."
        ),
    )
    # NB: the field NAME keeps its historical "scar_" prefix (renaming it would
    # orphan the value in every existing save); only the label is current. The
    # commander-capture mechanic the old label referenced was removed 2026-07-01 —
    # what remains is the command-post recon fog itself.
    scar_command_post_intel: bool = boolean_option(
        "Hidden enemy command posts (map the command network by recon)",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        default=True,
        invert=False,
        detail=(
            "Enemy command posts stay hidden on the map until you discover them — "
            "strike near them, scout them, or photograph them on a TARPS pass — so "
            "mapping the enemy command network is itself a reconnaissance task. On "
            "by default for new campaigns; existing campaigns keep whatever they "
            "were saved with. Turn it off to restore plain enemy command-post "
            "visibility."
        ),
    )
    aircraft_per_recovery_tanker: int = bounded_int_option(
        "Number of aircraft per recovery tanker",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        default=4,
        min=2,
        max=12,
        detail=(
            "A higher number makes the auto-planner generate fewer recovery tankers."
        ),
    )
    oca_target_autoplanner_min_aircraft_count: int = bounded_int_option(
        "Minimum number of aircraft (at vulnerable airfields) for auto-planner to plan OCA packages against",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        default=20,
        min=0,
        max=100,
        detail=(
            "How many aircraft there have to be at an airfield for "
            "the auto-planner to plan an OCA strike against it."
        ),
    )
    ownfor_autoplanner_aggressiveness: int = bounded_int_option(
        "OWNFOR auto-planner aggressiveness (%)",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        default=20,
        min=0,
        max=100,
        detail=(
            "Ratio of the threat-radius that will be ignored by the OWNFOR "
            "auto-planner. 0% means the entire threat-radius is considered, "
            "while 100% would have the auto-planner completely ignore OPFOR air defenses."
        ),
    )
    opfor_autoplanner_aggressiveness: int = bounded_int_option(
        "OPFOR auto-planner aggressiveness (%)",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        default=20,
        min=0,
        max=100,
        detail=(
            "Ratio of the threat-radius that will be ignored by the OPFOR "
            "auto-planner. 0% means the entire threat-radius is considered, "
            "while 100% would have the auto-planner completely ignore OWNFOR air defenses."
        ),
    )
    ownfor_planner_unpredictability: int = bounded_int_option(
        "OWNFOR auto-planner unpredictability (%)",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        default=0,
        min=0,
        max=100,
        detail=(
            "How much the OWNFOR auto-planner varies which opportunistic targets "
            "(strikes, OCA, BAI, anti-ship, non-threatening SAMs) it services first. "
            "0% keeps the deterministic, strict-priority planner; higher values let "
            "it sometimes service a lower-priority target first so its offensive "
            "target selection is less repetitive turn to turn. Reactive defensive "
            "tasking is unaffected."
        ),
    )
    opfor_planner_unpredictability: int = bounded_int_option(
        "OPFOR auto-planner unpredictability (%)",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        default=0,
        min=0,
        max=100,
        detail=(
            "How much the OPFOR auto-planner varies which opportunistic targets "
            "(strikes, OCA, BAI, anti-ship, non-threatening SAMs) it services first. "
            "0% keeps the deterministic, strict-priority planner; higher values let "
            "it sometimes service a lower-priority target first so red's offensive "
            "target selection is less repetitive turn to turn. Reactive defensive "
            "tasking is unaffected."
        ),
    )
    region_priorities: bool = boolean_option(
        "Region priorities (per-objective planning emphasis)",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        default=False,
        detail=(
            "Weight the BLUE auto-planner's offensive target selection by a "
            "priority set per control point: an emphasized region's targets rank "
            "as if at half their distance, a deprioritized region's as if at "
            "double, and an ignored region is left to manual packages entirely. "
            "A weight on your own planning, never a fence -- manual packages, "
            "ROE and rescue tasking are unaffected, and the enemy planner never "
            "reads it."
        ),
    )
    hq_priority_targets: bool = boolean_option(
        "HQ priority targets (weight by what a loss costs the enemy)",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        default=False,
        detail=(
            "Weight the BLUE auto-planner's offensive target selection by what "
            "losing each target costs the enemy, measured against others of its "
            "kind: enemy income for a factory, front-line vehicles for an ammo "
            "depot, the offensive package ceiling for a command post, and the "
            "equipment's price for everything else. The top third of each kind "
            "ranks as if at three quarters of its distance and the bottom third "
            "at one and a quarter, gentler than Region priorities so your own "
            "emphasis still outranks it. Sites hidden on your map are left "
            "alone, and the enemy planner never reads it. The target panel's "
            "Why it matters line shows the measure either way."
        ),
    )
    c2_decapitation_effects: bool = boolean_option(
        "Command-center kills degrade enemy planning",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        default=False,
        detail=(
            "Destroying a side's IADS command centers makes its auto-planner "
            "sloppier: as the command network is decapitated, its offensive target "
            "selection gets progressively more unpredictable (the same lever as the "
            "auto-planner unpredictability settings on the Air Doctrine page, scaled "
            "by how many command posts are down), and its offensive tempo thins -- "
            "a decapitated HQ frags fewer "
            "offensive packages per turn (never zero; the floor keeps some pressure "
            "on). So bombing the enemy HQ is a strategic move, not just a strike "
            "checkbox. Reactive defensive tasking is never affected -- a headless "
            "enemy still defends itself, it just plans worse offense. Applies to "
            "whichever side loses its command posts; a campaign with no command "
            "centers is unaffected."
        ),
    )
    weather_aware_planning: bool = boolean_option(
        "Auto-planner reads the weather",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        # Stock default (2026-08-09 re-convergence): upstream ignores weather.
        # RetLab planner suite preset turns this on.
        default=False,
        detail=(
            "The theater commander accounts for the sky when planning (both "
            "sides). In rain or thunderstorms the automatic photo-recon add-on "
            "stays home (cameras photograph cloud deck), and a thunderstorm "
            "pushes low-level visual attack -- front-line CAS, battle-position "
            "BAI, convoy interdiction -- to the back of the offensive plan so "
            "weather-tolerant strikes claim the jets first. Clear skies change "
            "nothing, and player-planned flights are never touched."
        ),
    )
    single_sead_escort_flavour: bool = boolean_option(
        "One SEAD flavor per package",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        # Stock default (2026-08-09 re-convergence): upstream sets the SEAD and
        # jammer flags off one radar-SAM trigger, so a package can pull SEAD
        # Escort, SEAD Sweep and (on DEAD) a SEAD flight at once. RetLab
        # planner suite preset turns this on.
        default=False,
        detail=(
            "SEAD Escort, SEAD Sweep and the DEAD package's own SEAD flight all "
            "answer the same radar-SAM trigger, so one package could pull three "
            "suppression flights while the package that actually needed them flew "
            "with none -- a flown Sinai plan put three Growler flights around two "
            "Harriers attacking a vehicle group and left the EWR strike unescorted. "
            "With this on a package takes the first suppression flavor proposed "
            "and no more. Fighter escorts are unaffected: an anti-ship package "
            "still doubles them deliberately to saturate a ship's air defenses."
        ),
    )
    front_line_sead_escort: bool = boolean_option(
        "Front-line CAS takes a SEAD escort",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        # Stock default: upstream's CAS package proposes only a SEAD Sweep, which
        # the Sidearm Harrier cannot fly. RetLab planner suite turns this on.
        default=False,
        detail=(
            "A CAS package on the front line also asks for a SEAD escort that rides "
            "with the CAS flight when radar SAMs cover its route or the enemy's "
            "front-line units include radar air defense. Airframes marked "
            "front-line-only for this job (the Sidearm-armed AV-8B) are preferred "
            "for it and no longer escort deep packages, where their missiles cannot "
            "reach the SAMs; deep packages keep the HARM shooters."
        ),
    )
    route_around_sams: bool = boolean_option(
        "Packages route around SAMs they don't need to enter",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        # Stock default: upstream flies JOIN->INGRESS and TARGET->SPLIT straight.
        # RetLab planner suite turns this on.
        default=False,
        detail=(
            "The legs from the join point to the ingress point and from the target "
            "to the split point are straight lines, and can cut through a SAM ring "
            "that has nothing to do with the target. With this on, those legs get "
            "nav points that take the package around the edge of any such ring. "
            "Rings covering the target are still flown through. Helicopters are "
            "unaffected."
        ),
    )
    tarcap_behind_sead: bool = boolean_option(
        "TARCAP arrives with the package's SEAD, not before it",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        # Stock default: upstream starts TARCAP 2 min before the package's join.
        # RetLab planner suite turns this on.
        default=False,
        detail=(
            "A TARCAP orbits over the target and normally starts 2 minutes before the "
            "package reaches its join point, which can put it over the target's SAMs "
            "long before anyone suppresses them. With this on, a TARCAP in a package "
            "that has a SEAD, SEAD Sweep, SEAD Escort or DEAD flight starts its orbit "
            "no earlier than the first of those flights' time over target. Packages "
            "without one are unchanged."
        ),
    )
    sead_strike_coordination: bool = boolean_option(
        "Strikes push behind their SEAD window",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        # Stock default (2026-08-09 re-convergence): upstream times packages
        # independently. RetLab planner suite preset turns this on.
        default=False,
        detail=(
            "Packages used to be timed independently, so a strike could arrive "
            "at a defended target half an hour before the SEAD package tasked "
            "against the SAM covering it. With this on, each side's AI "
            "strike, BAI, OCA and CAS packages whose target sits inside a SAM "
            "threat ring that a SEAD/DEAD package is servicing are retimed into "
            "the window just behind it -- SEAD opens the corridor, then the "
            "strikes push, several packages massing behind one suppressor. "
            "Player packages are never rescheduled, but a player-flown SEAD "
            "still opens a window the AI pushes behind."
        ),
    )
    max_escort_jammers: int = bounded_int_option(
        "Max escort jammers airborne per side",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        # Stock default (2026-08-09 re-convergence): upstream plans no escort
        # jammers. RetLab planner suite preset sets 4.
        default=0,
        min=0,
        max=12,
        detail=(
            "Caps how many escort-jamming flights (dedicated jammers -- the EA-18G "
            "Growler / EA-6B Prowler) each side's auto-planner will frag in one "
            "turn. Escort jammers are proposed on "
            "every radar-SAM-threatened package, so a strike-heavy turn against a "
            "dense IADS could otherwise put a dozen jammers in the air. The bubble "
            "and SAM-suppression effects don't stack (a missile faces one bubble, a "
            "SAM always gets a shoot-back window), so this is mostly an "
            "airframe-economy bound -- 0 disables auto-planned jammers entirely, "
            "leaving only any you plan yourself."
        ),
    )
    heli_combat_alt_agl: int = bounded_int_option(
        "Helicopter combat altitude (feet AGL)",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        default=200,
        min=1,
        max=10000,
        detail=(
            "Altitude for helicopters in feet AGL while flying between combat waypoints."
            " Combat waypoints are considered INGRESS, CAS, TGT, EGRESS & SPLIT."
            " In campaigns in more mountainous areas, you might want to increase this "
            "setting to avoid the AI flying into the terrain."
        ),
    )
    heli_cruise_alt_agl: int = bounded_int_option(
        "Helicopter cruise altitude (feet AGL)",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        default=500,
        min=1,
        max=10000,
        detail=(
            "Altitude for helicopters in feet AGL while flying between non-combat waypoints."
            " In campaigns in more mountainous areas, you might want to increase this "
            "setting to avoid the AI flying into the terrain."
        ),
    )
    atflir_autoswap: bool = boolean_option(
        "Auto-swap ATFLIR to LITENING",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        default=True,
        detail=(
            "Automatically swaps ATFLIR to LITENING pod for newly generated land-based F/A-18 flights "
            "without having to change the payload. Takes effect from the next turn."
        ),
    )
    ai_jettison_empty_tanks: bool = boolean_option(
        "Enable AI empty fuel tank jettison",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        default=False,
        detail="AI will jettison their fuel tanks as soon as they're empty.",
    )
    ai_vertical_takoff_landing: bool = boolean_option(
        "AI helicopters use vertical takeoff and landing",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        default=False,
        detail="AI will use vertical takeoff and landing instead of combat takeoff and landing.",
    )
    min_plane_altitude_offset: int = bounded_int_option(
        "Altitude scatter - lowest (x1000 ft)",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        min=-5,
        max=5,
        default=-2,
        detail=(
            "Airplane flights, player flights included, are nudged off their planned "
            "altitude by a random amount so they don't all stack at the same height. "
            "This is the lowest nudge (use a "
            "negative value for below). Set lowest and highest to the same value to "
            "turn scatter off - both 0 for none."
        ),
    )
    max_csar_flights: int = bounded_int_option(
        "Maximum CSAR flights planned per side each turn",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        default=2,
        min=0,
        max=10,
        detail=(
            "Maximum number of CSAR rescue packages the auto-planner will commit to in a "
            "turn, for each coalition."
        ),
    )
    max_plane_altitude_offset: int = bounded_int_option(
        "Altitude scatter - highest (x1000 ft)",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        min=-5,
        max=5,
        default=2,
        detail=(
            "The highest nudge (positive is above the planned altitude). Examples: "
            "lowest -2 / highest +2 scatters within 2,000 ft; lowest 0 / highest +4 "
            "only ever climbs."
        ),
    )
    min_patrol_altitude: int = bounded_int_option(
        "Minimum patrol altitude (x1000 ft)",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        min=0,
        max=40,
        default=0,
        detail=(
            "Raises CAP and patrol flights that would otherwise fly below this. "
            "Flights already planned higher are left alone. 0 turns it off (each "
            "aircraft uses its preferred altitude). Example: 28 keeps all CAP at "
            "28,000 ft or above."
        ),
    )
    player_startup_time: int = bounded_int_option(
        "Player startup allowance (minutes)",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=GENERAL_SECTION,
        default=10,
        min=0,
        max=100,
        detail=(
            "Time reserved for player startup before taxi (AI uses 2 minutes). "
            "Re-plan packages after changing this value."
        ),
    )
    # Doctrine Distances Section
    airbase_threat_range: int = bounded_int_option(
        "Airbase threat range (NM)",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=DOCTRINE_DISTANCES_SECTION,
        default=100,
        min=0,
        max=300,
        detail=(
            "Will impact both defensive (BARCAP) and offensive flights. Also has a performance impact, "
            "lower threat range generally means fewer BARCAPs are planned."
        ),
    )
    max_threat_range: int = bounded_int_option(
        "Maximum threat range (NM)",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=DOCTRINE_DISTANCES_SECTION,
        default=200,
        min=60,
        max=500,
        detail=(
            "Provides an upper limit to threat-ranges to avoid partial nav-meshes, which leads to errors. "
            "Lower this setting further if the map's bounds aren't covered by the nav-mesh."
        ),
    )
    cas_engagement_range_distance: int = bounded_int_option(
        "CAS engagement range (NM)",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=DOCTRINE_DISTANCES_SECTION,
        # Stock default (2026-09-22 DM call, extending the 08-09 re-convergence);
        # the RetLab planner suite sets 15.
        default=10,
        min=0,
        max=100,
    )
    armed_recon_engagement_range_distance: int = bounded_int_option(
        "Armed Recon engagement range (NM)",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=DOCTRINE_DISTANCES_SECTION,
        # Stock default, as above; the RetLab planner suite sets 10.
        default=5,
        min=0,
        max=25,
    )
    sead_sweep_engagement_range_distance: int = bounded_int_option(
        "SEAD Sweep engagement range (NM)",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=DOCTRINE_DISTANCES_SECTION,
        default=30,
        min=0,
        max=100,
    )
    sead_threat_buffer_min_distance: int = bounded_int_option(
        "SEAD Escort/Sweep threat buffer distance (NM)",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=DOCTRINE_DISTANCES_SECTION,
        default=5,
        min=0,
        max=100,
        detail=(
            "How close to known threats will the SEAD Escort / SEAD Sweep engagement zone extend."
        ),
    )
    tarcap_threat_buffer_min_distance: int = bounded_int_option(
        "TARCAP threat buffer distance (NM)",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=DOCTRINE_DISTANCES_SECTION,
        default=20,
        min=0,
        max=100,
        detail=("How close to known threats will the TARCAP racetrack extend."),
    )
    aewc_threat_buffer_min_distance: int = bounded_int_option(
        "AEW&C threat buffer distance (NM)",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=DOCTRINE_DISTANCES_SECTION,
        default=80,
        min=0,
        max=300,
        detail=(
            "How far, at minimum, will AEW&C racetracks be planned "
            "to known threat zones."
        ),
    )
    tanker_threat_buffer_min_distance: int = bounded_int_option(
        "Theater tanker threat buffer distance (NM)",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=DOCTRINE_DISTANCES_SECTION,
        default=70,
        min=0,
        max=300,
        detail=(
            "How far, at minimum, will theater tanker racetracks be "
            "planned to known threat zones."
        ),
    )
    max_mission_range_planes: int = bounded_int_option(
        "Auto-planner maximum mission range for airplanes (NM)",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=DOCTRINE_DISTANCES_SECTION,
        default=150,
        min=150,
        max=1000,
        detail=(
            "The maximum mission distance that's used by the auto-planner for airplanes. "
            "This setting won't take effect when a larger "
            "range is defined in the airplane's yaml specification."
        ),
    )
    max_mission_range_helicopters: int = bounded_int_option(
        "Auto-planner maximum mission range for helicopters (NM)",
        page=CAMPAIGN_DOCTRINE_PAGE,
        section=DOCTRINE_DISTANCES_SECTION,
        default=100,
        min=50,
        max=1000,
        detail=(
            "The maximum mission distance that's used by the auto-planner for helicopters. "
            "This setting won't take effect when a larger "
            "range is defined in the helicopter's yaml specification."
        ),
    )
