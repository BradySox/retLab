# Kola — Northern Flank 1985

RetLab's first campaign on the Kola map. September 1985: the Soviets hold Finnmark and are
pushing down the one coast road toward Bardufoss, the Northern Fleet is out of Murmansk, and
Sweden and Finland are neutral.

Owner: this note. CI lock: `tests/retlab/test_northern_flank.py`.

| | |
|---|---|
| Files | `resources/campaigns/northern_flank_1985.yaml` + `.miz` |
| Build tool | `python tools/build_northern_flank_miz.py` — **never hand-edit the `.miz`** |
| Routes | `python tools/supply_route_geo.py northern_flank_1985` and `northern_flank_1985_lanes` |
| Factions | `NATO Northern Flank 1985`, `USSR Northern Fleet 1985` — stock DCS units only |
| Source laydown | Starfire's `exercise_able_archer.miz`, which **still ships unchanged** |
| Checklist row | B207 |

DM calls, 2026-10-10: this campaign over a 2026 one and a Sweden-alone one; medium size;
stock units only; the Hornet, Viper and Apache are in with weapons held to 1985; a September
start.

---

## Why it exists

The three Kola campaigns the fork ships are upstream's (Able Archer 83, Operation Frostbite,
The Anvil of War). All three are a land push east to Murmansk with Sweden and Finland
fighting on NATO's side. None uses the sea, a neutral border, or 18 of the map's 37 airfields.

This one differs in three ways:

- **Sweden and Finland hold nothing.** §98 reads a country with no airfield as uninvolved and
  stands its border SAMs. The short way round the front is closed to both sides.
- **The sea is half the war.** A carrier group, two Northern Fleet groups, two Soviet supply
  lanes and two coastal batteries, with §81 naval magazines on.
- **Blue starts on defense.** The front opens at the Lyngen position, 40 NM from Bardufoss.

---

## The laydown

Twelve control points on one road.

| Side | Base | Stands | Used | Squadrons |
|---|---|---|---|---|
| Blue | **Carrier** (CVN-71) | 90 | 53 | F-14A 12 + 12, A-6E 10, F/A-18C 12, A-6E tanker 4, E-2C 3 |
| Blue | **Bodo** | 94 | 16 | F-15C 12, KC-135 2, E-3A 2 |
| Blue | **Evenes** | 57 | 25 | F-16CM 12, F/A-18C 12, KC-135 MPRS 1 |
| Blue | **Andoya** | 68 | 21 | F-4E 12, S-3B 4, B-52H 3, C-130J 2 |
| Blue | **Bardufoss** | 73 | 30 | A-10A 12, F-5E 8, AH-64D 6, UH-1H 4 |
| Red | **Alta** | 10 | 9 | Su-25 6, Mi-24P 3 |
| Red | **Banak** | 26 | 22 | MiG-23MLD 10, Su-17M4 8, Mi-8 4 |
| Red | **Kirkenes** | 10 | 8 | Mi-24P 4, Mi-8 4 |
| Red | **Koshka Yavr** | 21 | 20 | Su-25 8, Su-24M 8, MiG-23MLD 4 |
| Red | **Severomorsk-1** | 67 | 24 | Su-24M 10, MiG-25PD 8, Tu-142 2, A-50 2, An-26 2 |
| Red | **Olenya** | 67 | 20 | Tu-22M3 8 + 6, Tu-95MS 4, IL-78M 2 |
| Red | **Monchegorsk** | 96 | 26 | MiG-31 12, Su-27 8, MiG-25RBT 4, IL-76 2 |

20 blue squadrons with 145 aircraft; 23 red with 129.

**Roads** (`supply_routes:`, traced from real road lat/lon): Evenes – Bardufoss – Alta – Banak –
Kirkenes – Koshka Yavr – Severomorsk-1 – Olenya – Monchegorsk. The only opposed pair is
Bardufoss – Alta, so there is one front.

**Sea lanes** (`shipping_lanes:`): Bodo – Evenes, Bodo – Andoya, Severomorsk-1 – Kirkenes,
Kirkenes – Banak. Bodo and Andoya have no road link, as in Able Archer.

**Distances**: Bardufoss to Alta 115 NM straight, about 135 NM by road. The carrier sits 30 NM
north-west of Andenes, 390 NM from Severomorsk. Andoya to Olenya is 385 NM.

### The front starts at the Lyngen position

`control_point_strengths: {Bardufoss: 0.3}`. The front sits at strength × route length from
the blue base, which puts it near Skibotn. Without it the front opens half-way to Alta.

### Reinforcement

Ground units recruit anywhere on turn 0 and at factories afterwards. Blue's factories are at
Bodo and Evenes; red's are at Severomorsk-1 and Monchegorsk. Red's units reach the front by
the two sea lanes (Severomorsk – Kirkenes – Banak) or six road hops, so **sinking the supply
ships is how blue starves the spearhead.**

---

## What the build tool does

It loads `exercise_able_archer.miz` and applies edits that file cannot express:

1. **Ownership.** The eleven fields above are set; every other field goes neutral.
2. **Inherited markers are filtered.** A marker is kept when it stands within 100 km of a
   campaign field, outside Sweden and Finland (polygons from `resources/borders/kola.yaml`),
   and more than 5 km from a dropped FOB. Kept: 17 AAA, 11 short-range SAM, 5 medium SAM,
   1 long-range SAM, 9 garrisons, 7 motor pools, 2 EWR, 2 Scud sites, 114 trigger zones.
3. **Replaced, not kept:** the M-113 path groups and convoy-spawn markers (the yaml routes
   replace them), every ship group, the LHA, the two neutral FOBs and their pads.
4. **Bodo's long-range marker is re-banded** to medium at the same spot. Nothing NATO fielded
   in north Norway in 1985 fills the long band, and an unfillable marker never populates.
5. **Added:** 28 land markers, two coastal batteries, three C2 cells, four factories, seven
   ammunition depots, the carrier, and three ship markers.

Running it twice produces the same report.

### How added markers are placed

There is no elevation data offline, so the tool cannot measure slope. It uses the landmap:

- **SAM markers** search along the runway's extended centreline first, then rings. A runway is
  built along a valley floor, which is the best stand-in for flat ground available.
- **Guns, point defence, garrisons and buildings** take ground within 6 km before clear ground
  further out. None of them levels a launcher, and a gun 14 km out defends nothing.
- "Clear" means inside a landmap inclusion zone and outside every exclusion zone. Where no
  clear point is in reach the tool falls back to inclusion-only ground and names the marker.
- Every added marker is at least 3 km from its field and 900 m from every other marker.

18 markers needed the fallback, all guns, point defence, garrisons or buildings at Evenes,
Bardufoss, Alta and Bodo. **No SAM battery did.** Every medium and long battery stands on
ground the landmap calls clear; several sit 10 to 13 km from their field because that is
where the clear ground is. Row B207 flies the check that the launchers stand level.

`airfield_clearance_conflicts()` reports **zero** objects inside a runway strip or 80 m of a
stand on a fresh game.

---

## Traps this build hit

### Luostari has no jet stands

All 27 of Luostari Pechenga's stands are helicopter pads (`airplanes: False` in the pydcs Kola
data). The plan named it as the Soviet border jet field; a MiG-23, Su-24 or Su-25 has
nowhere to park. **Koshka Yavr**, 10 NM south-east on the same road, has 21 stands that all
take a jet and replaced it. `test_no_base_oversubscribes_a_stand_class` asserts every squadron
has at least one stand that fits.

### A neutral field with dynamic spawn loads as red

The source marks Koshka Yavr neutral with dynamic spawn. pydcs answers `is_neutral()` True
only for that combination, and this fork's loader reads any such field as a red control
point (it is one in Able Archer). The tool clears `dynamic_spawn` on every field outside the
campaign. Its red influence-zone trigger is dropped too; the loader raises on a zone naming a
control point that no longer exists.

### Big aircraft compete for a handful of stands

| Field | Stands that take a B-52, KC-135, E-3 or C-130J |
|---|---|
| Bodo | 4 |
| Andoya | 5 |
| Evenes | 1 |
| Bardufoss | 1 |

The first cut put four bombers, four tankers, two AWACS and two transports at Bodo: twelve
aircraft on four stands. Bodo keeps two tankers and two AWACS, Andoya takes three B-52s and
the Hercules, and Evenes holds one drogue tanker for the Hornets ashore. Alta is the same
problem in small: ten stands, six that take a jet and nine a helicopter, overlapping.

### The landmap calls the Norwegian coast sea

The Kola landmap is coarse on the coast. Bodo, Andoya, Alta, Banak and Kirkenes all sit in
what it reports as sea, and within 15 km of Evenes or Bardufoss 1 to 2 % of the ground is
clear. Measured as the share of a 10 km-wide band along each road that is clear:

| Road | Clear | Longest dead stretch |
|---|---|---|
| Bardufoss – Alta (the front) | 20 % | 21 km |
| Able Archer's eight path groups | 26 – 64 % | 3 – 78 km |

The front road is at the low end of what Able Archer already fights on, with a shorter dead
stretch than five of its eight. The front generator snaps to the nearest drivable ground, so
the fight will form in the valley pockets (Nordkjosbotn, Skibotn, Storslett) and not on the
mountains between them.

### Mod-gated airframes in a stock campaign

The A-7E, EA-6B, A-6A, Su-15 and Tu-128 are all behind mod toggles, and the T-62 is not a
unit the faction loader knows. None is in either faction. The S-3B Tanker is stock but
is rostered by no shipped faction (`test_s3b_viking_sea_control.py`); the carrier tanker
is the A-6E. `test_both_factions_are_stock_dcs`
applies every mod toggle off and asserts nothing is stripped.

---

## Settings it preseeds

| Setting | Why |
|---|---|
| `restrict_weapons_by_date`, `restrict_props_by_date` | The Lot 20 Hornet, Block 50 Viper and Apache stand in for the F/A-18A, F-16A and AH-64A |
| `neutral_border_defense` (+ `neutralborder` plugin) | Sweden and Finland |
| `naval_magazines`, `naval_weapon_release_stagger` (+ `navalmagazines` plugin) | §81 |
| `ownfor_default_qra_reserve: 2`, `opfor_default_qra_reserve: 2` | §1; Bodo's Eagles and the Kola interceptors |
| `c2_decapitation_effects` | Three C2 cells are authored (Severomorsk, Olenya, Banak) |
| `max_mission_range_planes: 400` | A cap on each airframe's own range; opens Murmansk to the bombers |
| `airbase_threat_range: 300` | Patrols. See below |
| `squadron_start_full` | |

**Patrol range (DM call 2026-10-10).** A base gets a BARCAP only when an enemy airfield is
inside `airbase_threat_range`. The nearest opposed fields, Alta and Bardufoss, are 116 NM
apart, so at the stock 100 NM neither side patrolled a land base: on turn 2 red flew no
patrol and left 20 interceptors idle. Measured by re-planning that turn headless:

| Range, on-station time | Red patrols | Blue patrols | Raids lost |
|---|---|---|---|
| 100 NM, 60 min (stock) | 0 | 2 (carrier) | none |
| 300 NM, 60 min (**chosen**) | 3 to 4 pairs: Alta, Banak, Kirkenes, Koshka Yavr | 6 pairs: the carrier and the four land bases | none |
| 200 NM, 30 min | 6 pairs | 15 pairs | blue: 2 of 5 strikes |
| 300 NM, 30 min | 12 pairs | 18 pairs | red: the carrier strike; blue: 3 strikes and a DEAD |

Severomorsk-1, Olenya and Monchegorsk are over 300 NM from any blue field and get no
patrol at any setting; their cover is the QRA pair and the SAMs. The setting is shared by
both sides. A campaign's settings apply to new games only.

Left off on purpose: GPS jamming and ship-launched cruise missile raids. Neither is 1985 kit
for the side that would use it here.

`ground_forces:` pins seven SAM markers to a system (SA-6 at the captured fields, SA-2/3/5/10
at home) and the two Barents ship markers to `Northern Fleet Surface Group` and `Northern
Fleet Landing Group`. The landing group uses the `Naval Two Ship` layout because the standard
naval layout has no landing-ship slot.

`victory:` — win by holding Alta, Banak and Kirkenes from turn 6; lose by losing Evenes.

---

## Anachronisms, accepted

- **CVN-71** was commissioned in October 1986. It is the Nimitz-class hull DCS has, and the air
  wing on it is close to the real CVW-8 of the period (VF-41, VA-35).
- **F/A-18C Lot 20, F-16CM Block 50, AH-64D** for the F/A-18A, F-16A and AH-64A (DM call).
- **Kirov and Slava** are the DCS hulls *Pyotr Velikiy* and *Moskva*.
- **M109A6** stands in for the M109A3; **M60A3** for Norwegian M48A5s and Marine M60A1s.
- Squadron presets are the nearest that exist. No Norwegian F-16 or F-5 preset is in the repo,
  and five red airframes have no preset at all (listed in the test).

---

## Not verified

Everything above is measured headless. A fresh game builds, both sides plan a first turn, and
the 14 lock tests pass. **Nothing has been flown.** Row B207 covers the first flight:

- the SAM launchers stand level and raise;
- the front forms on drivable ground near Skibotn;
- a Swedish or Finnish battery warns a player who crosses;
- supply ships sail the two Soviet lanes;
- Bodo, Andoya and Alta park what the yaml asks without a spawn failure.

The real-world basing and unit details here are from general knowledge, not checked against
sources.
