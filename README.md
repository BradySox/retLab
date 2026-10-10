# RetLab — a development fork of DCS Retribution

A development fork of [DCS Retribution](https://github.com/dcs-retribution/dcs-retribution),
the turn-based dynamic campaign generator for
[DCS World](https://www.digitalcombatsimulator.com/en/products/world/).

Based on upstream `dev` at `dce851ea`, plus this fork's feature set and selected later
upstream fixes. The unmodified upstream README is kept as
[`README.upstream.md`](README.upstream.md).

This is not a replacement for DCS Retribution and is not offered as one. It exists so the
features here can be built and flown before they are carved back upstream. If you want a
supported build, use [DCS Retribution](https://github.com/dcs-retribution/dcs-retribution).

> **AI assistants:** read [`CLAUDE.md`](CLAUDE.md) first — architecture, feature locations,
> branch layout.

---

## Download

Pre-built `.exe` releases are published automatically on every push to `main`. No GitHub
account needed.

**[Download latest build](https://github.com/BradySox/RetLab/releases/tag/latest)**

1. Download `retlab-latest.zip`.
2. Extract anywhere.
3. Run `retribution_main.exe`.
4. Point it at your DCS World install on first launch.

`latest` is a rolling pre-release tracking current `main`. Versioned releases (`v1.x.x`) are
pinned campaign builds.

---

## What's different from upstream

Most of this is opt-in. Full list with toggles, defaults and known limitations:
[`docs/dev/retlab-features.md`](docs/dev/retlab-features.md).

### Recon and intelligence

- Every enemy site is on your map from turn one, at its real position. What is actually
  parked there — unit types, counts, threat and detection rings — stays hidden until you
  engage it.
- Fixed SAM sites (SA-2, SA-3, SA-5, SA-10/20, S-400, Patriot and Hawk) are always known: composition and rings from turn one.
  Mobile SAMs (SA-6, SA-11 and the rest) are fogged like any other site.
- Engaging means ordnance on the site, or any ground-attack sortie that reaches it. Recon
  overflight does not reveal.
- Once engaged, a site is known completely and permanently, damage included. There is no
  separate BDA pass to confirm what you killed.
- Enemy command posts are hidden outright — no marker, nothing to plan against. Flying TARPS
  recon over the area is the only way to find one, so the command network has to be mapped
  before it can be struck.
- Insurgent contacts — roadside IEDs, HVT convoys, dispersed cells — are the exception: they
  show as a dashed "somewhere in here" circle until you localize them.
  The radar SAM network does not move.
- TARPS is a player task (F-14, RF-101B, RA-5C), flown to locate command posts.
- Also: approximate target-area mode, mobile SAMs hidden from player datalink, a fog reveal
  toggle, DCS-accurate terrain charts as base map.

### Combat SAR and squadron missions

- An ejected pilot becomes a survivor on the campaign map and stays there across turns. Rescue
  them and they recover for a few turns, then return to duty. Nobody reaches them in time and
  they go missing in action. AI ejections count.
- Coming down beside a base settles it without a rescue: inside friendly lines the pilot walks
  back, inside enemy lines they are captured and held at that base. Take the base back and they
  come home.
- Several survivors close together are collected on one lift rather than one flight each.
- CSAR is a normal auto-planned mission type for both sides. Any helicopter with a cabin
  qualifies, and a human can fly the rescue in any CSAR-capable helo.
- The survivor keys an **ADF homing beacon on 260 kHz**, briefed on your kneeboard. Tune it
  before you launch — the C-130J, UH-1H and Mi-8 all home it directly.
- The C-130J flies the "King" on-scene commander role, on an orbit near the survivor rather
  than a pickup run. Add it to a rescue package by hand: the auto-planner never frags one,
  because DCS only lets helicopters land at an unprepared pickup site and an AI King would
  orbit a survivor it can never collect.
- The A-10 and the Apache fly the **Sandy** rescue escort: an armed track over the survivor,
  covering the pickup while the helicopter works. Add one to a rescue package by hand —
  the auto-planner never frags one, because coordinating a rescue is a job for a human.
- Flying the King, you find the survivor yourself: an F10 menu takes **DF cuts** on the
  beacon, two cuts from different positions make a fix, and inside pod range with line of
  sight the fix snaps exact. A **threat sweep** around the fix reports what is near the pilot
  as a class and a rough position — SAM, AAA, MANPADS, armour, troops — and **Pass picture**
  puts the brief and the marks on the Sandy's and the helicopter's own F10 map. The King
  cues; it never lases, and AI flights are never re-tasked.
- Two pickup styles: land and let the survivor walk aboard, or hoist them on a hover. A pilot
  down in the water is always hoisted.
- Survivors pop smoke for AI rescue flights. Human crews get the F10 menu — list active
  survivors, request smoke, flare or IR strobe — and choose when to expose the position.
- JAMMING turns the C-130J into an EC-130H/RC-130H-style EW and ISR platform.
- Escort jamming is flown by the EA-18G Growler and EA-6B Prowler only (both require their
  mods). The jammer spoofs radar missiles fired at anything under its bubble and pulses
  tracking SAMs to weapons-hold; effect strengthens with proximity. AI flies it automatically;
  players get an F10 menu. A per-side cap limits how many fly per turn.
- The auto-planner puts jammers on the packages that fly into a SAM ring — DEAD and strike.
  Helicopter packages (air assault, CSAR) do not get one; neither do their fast-jet formation
  escorts, which now follow the same helo/LHA rule the A2A and SEAD escorts already used.
- Fixed-wing transports fly Air Assault as a paradrop. Players run in below 3,000 ft AGL and
  use the CTLD *Unload / Extract Troops* call; AI releases automatically over the drop zone.
  Helicopter assaults are unchanged.
- Every generated mission is archived to a dated copy in a folder DCS's mission browser lists.

### Air war planning

- QRA intercept reserve holds fighters for base defence. Part of it can be player-manned as
  cold alert.
- A package flies the leg from the join to the ingress at one speed, so escorts stay with
  the strikers they are escorting instead of running ahead. Cruise speed is set per airframe
  where one has been measured rather than assumed the same for every jet; the F/A-18C is the
  first, and transits a little slower than before.
- Native DCS data cartridges auto-load in Hornets, Vipers and F-14B(U)s: route with push
  times, boat TACAN/ICLS/ACLS, Hornet radio presets named after what they tune (your
  flight, AWACS, tankers, PKG, JTAC, DEP/ARR/DVT), and the SA/HSD
  picture (the front line, your own orbit, the tankers and AWACS, recon-confirmed SAM
  rings). The front line is drawn as one continuous boundary with the same bulges the F10
  map shows, not a separate straight dash per front, and the tanker you can actually take
  gas from is drawn as a box you can see without selecting it. On the Viper HSD the land
  borders within 40 NM of the route come before the front line. The Hornet SA page draws
  one item of each kind: the nearest border dashed, the next border solid (the front line
  instead on CAS), the package's lane from the IP over the target, and its TACAN list
  holds the boats, your fields and the map's other TACANs nearest your route. The
  orbit shown is the flight's own — its patrol track, or its hold point when it flies no
  track — never another flight's station. Hornets get the bullseye designated as the
  air-to-air waypoint; Vipers get the friendly recovery fields as Destination steerpoints,
  the briefed divert first and the enemy field they are working over beside it. A
  per-flight DTC tab controls the cartridge or any single section of it.
- **My aircraft** (top bar) is one window for the seat you are flying: the points and
  drawings you saved for it, its payload and its data cartridge.
- Save a point from the map's crosshair button as a waypoint, IP, target, hold or orbit,
  or draw a line or an area. Each jet gets them where its cartridge has a place: Hornets
  and Vipers after the route on sequence 2, the F-14B(U) on flight plan 3, the Apache on
  route BRAVO, the A-10 in its navigation computer. Every aircraft gets them on a
  kneeboard page with the cockpit's own numbers.
- The DTC tab shows only what your aircraft's cartridge carries. You choose load at spawn
  or by hand, which kinds of waypoint go into the jet, and whether SAM rings are limited to
  the ones near your route or the long-range ones.
- A new flight's DTC tab starts with ticks for its task: the front line only on CAS, every
  known SAM on SEAD and DEAD, the SAMs with a 15 NM or wider ring on CAP, and the SAMs
  within 40 NM of the route on strike, CAS and escort. **Save as my default** keeps your
  own ticks for that aircraft and task, in every campaign.
- The F-14B(U) cartridge is built differently, because plan 1 of its navigation page is
  already the mission route. It leaves that alone and adds the front line as map lines, the
  bullseye, divert, tanker, AWACS and CAP anchors and the confirmed SAM sites as reference
  points, puts the flown route on plan 2 with its times, hands each station that carries a JDAM
  its own target as a pre-planned aimpoint with the run-in from the IP (every target stays
  selectable on every station), and fills the TIS send-to list with the rest of the package.
- A wing flying both boom and probe receivers gets a theater tanker of each, on separate
  orbits. A wing that only needs one method still gets one tanker.
- A tanker flight's **Waypoints** tab has **Set orbit speed**: the KIAS it flies on its track,
  to suit its receivers. **Save as default** on the Payload tab keeps it for every new flight
  of that airframe.
- A theater tanker flies a 40 NM racetrack. On the map, drag its first point to move the
  whole track, or its second point to swing the track around the first.
- A flight's **Waypoints** tab has **Refuel before the push**: the flight tanks at a theater
  tanker between Hold and Join, and leaves Hold earlier to make it; the TOT stays put. The
  stop after the strike stays only if the jet cannot get home without it, and the tab
  then says how many lb short it would be. AI flights fill to 90% there. **Minutes on the
  tanker** sets how long the stop is planned to take; it starts at 4 minutes a jet plus 1.
- BARCAP and TARCAP flights get **Refuel before station** on the same tab: the flight tanks
  at a theater tanker on its way out, and the race-track times stay put. A TARCAP's stop
  coming off station follows the same rule.
- Cold-start allowances follow the airframe where the time is known — a Viper aligns on a
  stored heading in seconds, a Phantom waits on its gyros. Everything else uses the
  campaign-wide setting.
- Tanker and AWACS orbits are drawn on the F10 map with callsign, frequency and TACAN.
  The box is as wide as the turn the aircraft actually flies, so the tanker stays inside
  the shape you are looking at.
- A flight only gets a tanker leg on its route when it needs the gas. A bomber that lands
  with most of its fuel no longer flies past its own field to a tanker first.
- The Payload tab shows the sortie's fuel plan live: planned burn, what the jet carries
  internally and in tanks, the RTB margin with no tanker, and how many tanker passes the
  route has. It flags a sortie that only gets home on a top-off, so you can add a bag or
  trim the route before you fly it.
- One continuous clock: time advances a few hours per turn and weather evolves from the
  previous turn instead of re-rolling. Requires day-and-night missions.
- The planner reads that weather — rain and storms ground automatic photo-recon and push
  low-level CAS and BAI behind all-weather strikes.
- Optionally fly the real sky: with the ATMOS-X cloud pack and its CLI installed, the turn's
  weather is a live METAR observation instead of a generated one. The campaign keeps its own
  date and time. Falls back to generated weather if the observation cannot be fetched.
- Strike packages headed into a defended area are timed just behind the SEAD servicing that
  SAM. Fly the SEAD yourself and the AI push forms behind you.
- Front-line CAS gets a SEAD escort, and the Sidearm-armed Harrier flies it. Harriers no
  longer escort deep packages their missiles cannot protect. Part of the RetLab planner suite.
- Packages route around SAM rings they do not need to enter on the way from the join to the
  target and back to the split, instead of flying straight through. Part of the RetLab planner
  suite.
- Edit a route on the map. With a flight selected, drag a point to move it, double-click
  the route to add a point there, and right-click a point to delete it.
- The way in and out of a package (join to IP, target to split) is flown by every flight
  together, so a point moved, added or deleted there changes every flight in the package.
  The package window's **Package route** button lists it.
- Insert NAV point in a flight's Waypoints tab adds a point beside any waypoint with a leg
  next to it. On the package route it asks whether the point is for the whole package.
- RetLab starts with its own splash, and a generated mission loads with a RetLab picture on
  the briefing screen. To use your own mission picture,
  save it as `briefing.png` or `briefing.jpg` in `Saved Games\DCS\Retribution`.
- The debrief grades each flight: on time at the target or not, the package target, kills,
  shots and hits, losses, and your fuel on landing against the jet's reserve. Grades run Unsat, Below average,
  Average, Above average, with the faults listed. Your flights come first.
- A TARCAP in a package with SEAD or DEAD arrives with the suppression, not up to 20 minutes
  ahead of it over the target's SAMs. Part of the RetLab planner suite.
- At a busy airfield, flights queue for the runway at 45 seconds per jet, and each flight
  spawns early by its wait. A quiet field keeps the flat 8 minutes.
- The mission starts up to 30 minutes before the turn's clock when a flight needs that long
  to make its TOT. TOTs and the campaign clock do not move, except that ASAP tankers, AWACS
  and the first CAP wave launch at the earlier start.
- Also: overlapping BARCAP waves, ASAP tankers and AWACS, weighted off-mission combat resolution, per-side
  planner unpredictability.

### Battlefield and world

- Troops In Contact produces prolonged, formation-aware frontline firefights.
- Supply columns run both sides' road networks. Friendly routes sometimes hide ambush teams;
  nothing is telegraphed before the TROOPS IN CONTACT call.
- Sea shipments sail as convoys of cargo ships, each carrying a share, so sinking some denies
  only their share. Coastal anti-ship batteries fire on enemy shipping in range.
- Ship groups generate as mixed task groups rather than copies of one hull. Patrol boats never
  join a cruiser screen; a navy with one hull of a class still gets a coherent group. New games
  only.
- Missile batteries generate with a support park — cargo trucks, transporter/loader, fuel
  bowser, and a command vehicle where the faction has one — in that nation's kit. Launchers
  now have a purchase and repair cost. New games only.
- Squadrons spawn under their own DCS country, giving nation-specific voiceovers and pilot
  names. A country selector sits in the Air Wing Configuration dialog; campaigns can pin
  `country:` per squadron.
- Carrier comms match the hull: TACAN and ident (Roosevelt 71X TRO, Stennis 74X STN), stable
  channels, the ship's real name. If a map beacon owns the hull channel the boat takes the
  nearest free one. Navy jets wear sequential per-squadron modexes, and a Tomcat squadron
  flies its CAG bird plus line jets rather than four copies of one airframe. The Payload tab
  can pin a Hornet or Tomcat flight's board number (the lead's; wingmen follow) and no other package reuses it.
- Carrier decks carry dressing — tractors, crash truck, deck crew, LSO team — placed clear of
  every parking spot and catapult, and standing for the whole mission.
- Carriers steam for wind down the **angled** deck, not the bow, using each hull's own deck
  angle (9° Nimitz, 10.5° Forrestal, 7.95° Kuznetsov). BRC sits up to 15° off the wind
  reciprocal — that is the ship's real heading. New missions only.
- Also: mixed frontline combat clusters, civilian traffic, RetLab-tuned Splash Damage 3.

### Kneeboards and debrief

- The kneeboard is the stock deck with RetLab content folded into it. Mission Info opens on a
  BLUF: task, target, TOT, code words, compact air and SAM threat picture, loadout summary,
  SAR drill.
- The fuel ladder rides in the flight plan with RTB margin called out. It charges the whole
  sortie including on-station orbit, so a CAP row shows patrol speed and an endurance line
  ("On station 45 min planned; fuel supports ~50 min before bingo").
- A SITREP page reports last turn: both sides' losses (the enemy's as claimed), base changes,
  pilots recovered.
- A Threat Intel Brief gives one card per enemy air-defence system — NATO name, guidance, ceiling,
  range, RWR symbol, how to beat it. It respects recon fog: un-engaged sites show only a threat tier.
- Mission code words are visible to planners before generation and on the kneeboard in the
  cockpit.
- **Set as default for &lt;task&gt;** in the payload editor pins a loadout for that airframe and
  task across campaigns until cleared. Fuel and cockpit settings are already remembered per
  airframe.
- The payload editor hides practice, captive, inert, smoke and illumination stores, TCTS
  pods and travel pods until **Show training and non-combat stores** is ticked. White
  phosphorus marking rockets are always listed.
- Also: target intel panels, impact-first debriefs, custom kneeboard import, era-gated cockpit
  options.

### Campaign systems

- **SP Pilot Mode.** The debrief gains an *Accept results & fly next* button that processes the
  turn and opens a sortie board instead of the map. Pick an aircraft from anything the wing can
  put up, then a sortie in it — one seat, AI wingmen. The role comes from what the package
  needs. A pre-turn brief covers evading pilots and their capture odds, enemy C2 damage,
  victory progress and the next squadron arrival. The map and mission planner are untouched.
- **Scheduled squadron arrivals.** Campaigns can add *new airframes* on announced turns, so the
  wing you start with is not the wing you end with. Schedules follow air-campaign order:
  air superiority, SEAD/DEAD and enablers first, deep strike once the SAM belt is coming down.
  Operation Baltic Fury and Red Tide ship with schedules.
- **Command-post strikes matter.** Destroying enemy command posts degrades its target selection
  and thins its offensive tempo. Reactive defence is unaffected.
- **The front line behaves like a front line.** Five changes, each its own setting. Bases only
  rebuild their strength if supply can still reach them — a road or sea route back recovers in
  full, air resupply alone at a quarter, cut off at nothing. Winning a battle on the offensive
  costs you part of the ground you took; winning dug in costs nothing. Where the line sits
  accounts for how much armour each side actually has there, not just an abstract strength
  figure. Bad going slows an advance, so fronts stall at passes and run in the open. And the
  line bows instead of running straight, showing salients where the ground is good. The line is
  drawn only across ground vehicles can actually drive on, so a front pinched into a pass is
  narrower than the width setting asks for rather than sitting on the ridge beside it.
  An arrow on the map shows which way each front moved last turn and how far; hover it for the
  distance and your own stance. Map layer **Front movement last turn**, under Front lines.
- **Missions report back.** Every flight's track, time airborne, fuel, shots and hits come home
  with the results, not just which aircraft died. The campaign summary says what the day's
  flying actually amounted to. No third-party software required.
- **Enemy procurement** favours its better hardware rather than rolling the catalogue. Optional
  SAM site repair regenerates a couple of units per turn unless pressured; command posts stay
  dead.
- **Victory conditions.** Campaigns can author them: hold objective bases, destroy named
  high-value targets, kill every command post, grind enemy air below a threshold, or deny all
  operating airfields. Any campaign can enable a domination or attrition ending from settings.
  The map ribbon shows a live checklist. The capture-everything ending always remains.
- **Cruise missile raids.** Mark a target and call the strike; the nearest warship ripples a
  salvo. Magazines are finite and never rearm. A launch alerts defending SAMs around the
  aimpoint.
  Automatic raids never fly past an enemy SAM site that has point defense.
- **Naval magazines.** Warships can be released to weapons-free a group at a time instead of
  all at once, and anti-ship missiles fired are gone for the rest of the war. A ship group also
  stops after a set number of anti-ship missiles per mission, so a fleet fights a running battle
  instead of emptying every tube in the opening minutes. A dry ship still defends itself.
- **GPS jamming.** A JDAM, JSOW, JASSM or SLAM-ER released inside an enemy jamming bubble flies
  its normal profile and lands off the aimpoint — further off the deeper inside you released.
  Laser and TV weapons are unaffected; killing the jammer restores accuracy immediately. A
  jamming site is briefed on the kneeboard once you have engaged it.
- **What's New.** A toolbar button lists the recent changes in the build you are running,
  newest first, each with a line saying what to look for in the next mission.
- **AI review of the enemy's turn.** Developer tools > Copy AI connect link gives an AI that
  can read web pages on your PC (Claude Code, for example) a read-only view of red's turn:
  forces, packages, routes, the air-defense network, last turn's losses and a map picture.
  Say "review the turn" and it reports what looks wrong in red's plan. It never sees your
  own packages. Tick **Developer tools > Outside AI plans red** and it plans red instead:
  packages, TOTs, front stances, buying and selling. The game still plans and buys for red
  at the start of every turn, so the AI starts from that plan and red is never empty.
  Ported from juanjux/dcs-escalation.
- **Target priorities.** Tell the auto-planner where to push and what to chase. Mark an enemy
  base emphasized, deprioritized or ignored from its base dialog; mark a single target the
  same way from its own dialog; and set a priority per kind of target — air defense,
  infrastructure, armor, naval and so on — in the Target Priorities window. A weight, not a
  fence: your own packages and rescue flights are never affected, and a target inside an
  ignored base can still be marked back on. Off by default.
- **HQ priority targets.** An enemy target's panel says why it matters: the income it earns
  the enemy, the front-line vehicles an ammo depot keeps fielded, how far a command post's
  loss cuts the enemy's offensive packages, or the price of the equipment on it, and where it
  ranks among others of its kind. With **HQ priority targets** on, the auto-planner leans
  toward the top third of each kind, more gently than Target priorities. Off by default.
- **Smart threat reaction.** One SAM launch no longer sends every jet in the area defensive.
  AI aircraft fly their route and use chaff and flares; only the flight the missile is
  actually guiding on breaks, and only until that missile is gone. The trade is that a flight
  facing a missile the engine will not resolve a target for flies straight instead of
  breaking, so AI losses in heavy SAM country can go up. Turn the plugin off for stock DCS
  behaviour.
- **Lua profiler (diagnostic).** A plugin for the flight where the sim keeps hitching. Off
  by default; tick it, regenerate, fly five minutes, untick it. It writes
  `Saved Games\DCS\Logs\MooseProfiler.txt` — which script is eating the sim thread, or
  proof that none is — and logs every stall over 250 ms to `dcs.log` with the mission
  time. The mission runs slower while it profiles.
- **The bullseye stays put, and the kneeboard says where it is.** The Bullseye line now
  names the place — `Bullseye: King Abdullah II — 32°00'20"N 36°13'25"E` — instead of
  only its coordinates. It is set once for the campaign and stays there, so the number
  you memorize on turn 3 is still good on turn 30, and it is never planted on a ship or
  an off-map field. On the rare turn the front carries it far enough that it has to
  move, the same line reads **MOVED THIS TURN**.
- **Neutral countries defend their borders.** Every nation on the map is drawn with its
  real border, on any campaign, with nothing to author — including the one the war is
  being fought in. Which side a country is on comes from who holds the airfields inside
  it, so it flips by itself when a base changes hands. A country that is *not* in the war
  and refuses you transit is the one that defends: it stands surface-to-air batteries
  inside its own border from the moment the mission starts, so you can find them before
  you cross rather than finding the border by tripping it. Both what it fields and how
  much of it scale with the country, and what it fields follows the era as well: a legacy
  campaign meets SA-2s, SA-3s and SA-5s, a modern one SA-10s and SA-11s, with Rapier,
  Hawk and Patriot for the nations on western kit. A small country gets a single
  short-ranged battery, a large one several long-ranged ones, spread along the stretch of
  frontier the war is actually near, each set back well short of what its missile
  claims, so the border sits inside the envelope with margin rather than on its edge. Cross and it
  warns you off the radio at once. Leave and nothing happens. Stay too long or release a
  weapon inside the border, and the whole country turns hostile and engages — not just
  the site you flew past. If both sides violate the same country, it puts up a second set
  for the other one.
  Whether a country lets you through is read off the map, not off the calendar: you may
  cross what your side flies from, and what both sides fly from; a country neither of you
  is based in has invited nobody. Altitude buys you nothing unless the campaign says so.
  AI flights that stray are never fired on (a plugin option holds them to the same rules, for testing), and
  the auto-planner does not route around the border, so it is your corner to cut or not.
  The same borders are drawn on the planning map and the F10 map. Off by default.
- **Pilots keep a logbook.** Every pilot carries a permanent record: sorties, combat sorties,
  hours airborne, air, ground and naval kills, ejections and a rank. Open it with the
  **Logbook** button in the squadron dialog. The numbers come from what the mission recorded,
  so a jet that never left the ramp logs nothing and a kill counts only when DCS names the
  killer and the two sides differ — you are never credited for a friendly. Ranks are read
  from a data file, so they suit the air force flying. It is a record, not a reward:
  nothing in it unlocks an aircraft, changes availability or gates a mission. A campaign
  carried over from an older build starts its careers at zero.
- **Your own logbook, across every campaign.** The per-pilot record above lives in the save,
  so a new campaign starts it over. This one does not: a **Pilot Logbook** button on the
  toolbar — it opens with no campaign loaded — shows your lifetime sorties, hours, kills by
  type, a breakdown of what you actually fly, the campaigns you have flown, and the
  individual flights. You are identified by your DCS player name, so there is nothing to set
  up, and a host running a squadron event records every pilot who flew, each to their own
  profile. It is kept in a file beside your other Retribution settings rather than in the
  save game, which is what lets it survive starting over.
- **A dynamic slot is not a blank jet.** With DCS dynamic slots on, each base's dynamic
  spawns of a type are built from a player flight of that type already fragged there, so
  a pilot who joins late and takes a dynamic Hornet gets that flight's loadout and
  properties, and its route and comm card if DCS carries them (not yet flown). The fragged
  flight still flies as itself. A type with no player flight at the base still spawns
  blank, and the times on target are the template's, so they go stale. Its own toggle
  sits under the dynamic slots setting.
- Also: strikeable motor pool depots, a host F10 menu to scramble bandits.

---

## Campaigns

| Campaign | Map | Setting |
|---|---|---|
| Red Tide | Germany | 1988 NATO counteroffensive through the Fulda Gap |
| 1968 Yankee Station | Caucasus | Vietnam air war, coastal ladder from Hanoi to the DMZ |
| Operation Enduring Resolve | Afghanistan | Living counterinsurgency |
| Red Flag 81-2 | Nevada | The exercise, played as the war it rehearses |
| Operation Inherent Resolve | Iraq | Battle of Mosul, 2016–17 |
| Umm al-Ma'arik | Iraq | Desert Storm 1991, fought from the H-3 strips inward |
| Second Island Chain | Marianas | 2027 China fight up the chain from Guam |
| Northern Flank 1985 | Kola | The coast road from Narvik to Murmansk, and the sea beside it |

- **Red Tide** — the Pact overran the Fulda Gap, took Hamburg and seized Copenhagen; the thrust
  has culminated. Every squadron is a named historical unit in matching livery. Fulda is a
  forward helo FARP under artillery fire.
- **1968 Yankee Station** — Hanoi inland behind its SA-2 ring, route packages laddering south to
  a DMZ front, carriers on Yankee Station, the Air Force crossing from the Thailand fields. The
  Ho Chi Minh Trail is a real, cuttable supply web.
- **Operation Enduring Resolve** — a fork of Starfire's *Operation Shattered Dagger*. Strongholds
  regenerate, throttled by hidden ammo caches you have to find and strike. Infiltrators creep
  toward ungarrisoned bases to take them. Body count alone wins nothing.
- **Red Flag 81-2** — Aggressor F-5Es, the Constant Peg MiGs out of Tonopah, an emulator SAM
  array, KS-19 flak belts. The Groom Lake box never opens.
- **Operation Inherent Resolve** — the insurgency holds Mosul, Erbil and Kirkuk plus ten
  furnished FOBs along Highway 1 and the Nineveh ring. Grind north from Balad against IEDs, HVT
  convoys and a 14-route supply web, under a permanent Mosul positive-control box.
- **Umm al-Ma'arik** — blue holds only the three H-3 desert strips seized on the border, with
  the tanker bridge and AWACS flying from the Saudi rear, and climbs the pipeline-road ladder:
  H-2, then Qadessiya (Al-Asad) where the Foxbats live, then the Habbaniyah line toward
  Baghdad. The French-built KARI network ties the SA-2/SA-3 rings back through sector operations
  centres to one destroyable ADOC — decapitate it and the net goes autonomous, leave it and it
  repairs. Night-one start (17 Jan 1991, 0300), a Scud hunt in the western baskets, real-highway
  convoy interdiction, and a GCI-alert Iraqi Air Force on hot-pad QRA. Every squadron is its
  real 1991 unit.
- **Second Island Chain** — a Taiwan crisis went kinetic; the opening salvo cratered Guam's ramps
  while amphibious groups took Rota, Tinian and Saipan. Hold the remaining ramp and fight north.
  A modern PLA air-defence belt (S-300PMU-2 on Tinian, HQ-22 on Rota, HQ-7 and HQ-17A point
  defence), road-mobile PLARF launchers, three PLAN carrier groups and a
  Badger regiment. Both fleets trade cruise missiles from finite magazines. The islands aren't
  connected, so no ground front forms — islands change hands by air assault, helicopter off the
  LHA or C-130J paradrop.
- **Northern Flank 1985** — the Soviets hold Kirkenes, Banak and Alta and push down the one
  coast road toward Bardufoss. Sweden and Finland are neutral and defend their borders, so
  nobody flies round the front. A carrier in the Norwegian Sea, the Northern Fleet out of
  Murmansk, Soviet supply ships to sink and Backfires hunting the boat. Stock DCS units only.

The Vietnam campaign layer also changes how the enemy fights: Hanoi answers the campaign clock
by surging the Trail or opening a Tet-style ground push on a scheduled window, and its MiGs fly
a period GCI ambush — scramble late, one slashing pass, run for home.

**Mod content:** CurrentHill Iran assets, the RetLab Iran Air Defense Pack (3rd Khordad and
Bavar-373, and the Sejjil-2, Emad, Kheibar, Fattah-2 and Shahed 238 missile sites; Retribution
support is in, the mod is not released yet), High Digit SAMs (Ultimate Compilation — S-400, SAMP/T,
Pantsir-SM, period EWRs), and the optional Expanded F-4E Weapons Pack (check it on the Mods page
to arm the Heatblur Phantom for Weasel SEAD; without the mod the jet falls back to stock Shrike
fits). Plus a rebuilt settings screen with difficulty presets and a seven-mechanic Vietnam Ops
page (Arc Light, flak gauntlet, naval gunfire, trail convoys, Super Gaggle, FAC(A) marking,
snake and nape).

Existing campaigns keep whatever settings they were saved with.

---

## Running from source

Same as upstream. Windows, PowerShell:

```powershell
.\scripts\bootstrap-env.ps1
.\scripts\check-env.ps1
.\venv\Scripts\python.exe -m qt_ui.main
```

You need a working DCS World install. MOOSE-dependent features assume the bundled plugins under
`resources/plugins/` are present. Full upstream setup and dependencies:
[`README.upstream.md`](README.upstream.md).

### Environment health

This repo is sensitive to Python drift on Windows. If `.venv` was created from a Python install
that later moved or was removed, every repo-local command fails the same confusing way.

```powershell
.\scripts\bootstrap-env.ps1  # find Python 3.11, recreate .venv, install requirements
.\scripts\check-env.ps1      # verify Python, venv, and Git LFS auth
```

`check-env.ps1` also warns on unauthenticated Git LFS, a common cause of push failures.

### Checks before pushing

```powershell
.venv\Scripts\python.exe -m black --check .      # formatting
.venv\Scripts\python.exe -m mypy game tests      # type checking
.venv\Scripts\python.exe -m pytest tests -q      # unit tests
```

---

## Relationship to the mission-building workspace

A separate, private mission-building workspace sits alongside this repo (campaign plans,
`.miz` files, and Mission-Editor scripts not yet integrated here).

These started as standalone ME scripts and are now integrated — do not use the standalone
versions:

- **C-130J EW/ISR** → `resources/plugins/c130j/` (`FlightType.JAMMING`). Supersedes the retired
  generic `ewrj` / "EW Jammer Script".
- **QRA / AI_A2A_DISPATCHER** → `resources/plugins/intercept/` (per-squadron `intercept_reserve`)

This repo is the engine-level side: capabilities planned and spawned by the campaign generator
rather than hand-placed in the Mission Editor.

---

## License

DCS Retribution is LGPL (see [`LICENSE`](LICENSE)). Upstream authorship and history are
preserved; RetLab additions are under the same terms.
Upstream: <https://github.com/dcs-retribution/dcs-retribution>.
