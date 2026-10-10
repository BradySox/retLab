# AGENTS.md — RetLab Agent Guide

**RetLab** — a development fork of DCS Retribution, a turn-based dynamic
campaign generator for DCS World, plus RetLab's air-defense, electronic-warfare,
recon, frontline, and assets-pack features on top of upstream.

- Forked from upstream `dcs-retribution/dcs-retribution` `dev` at `dce851ea`; later upstream
  fixes are adopted by hand (last sync #999, 2026-08-30).
- GitHub (this fork): https://github.com/BradySox/RetLab
- Read this before touching anything. The human-friendly overview is [`README.md`](README.md).

---

## Session Startup & Documentation Hygiene

**At the start of every new thread**, sync with GitHub before touching any code or docs:

```powershell
git fetch origin
git pull
git log origin/main -5 --oneline   # scan for new commits since last session
```

If the current branch is behind `main`, merge or rebase before editing anything — a branch
cut from a stale base produces duplicate work and conflicts. Never derive the state of the
codebase from memory; always read the current files.

**Keeping docs in sync** — when a feature lands or changes, update in this order. A push that
moves code past its docs is a broken push.

1. Relevant `docs/dev/design/` file — design rationale and technical details
2. Matching section in `docs/dev/retlab-features.md` — engineering deep-dive, file paths, gotchas
3. `README.md` — if the change is player-visible
4. `CLAUDE.md` — if the tech stack, architecture patterns, or feature list changed
5. `AGENTS.md` — sync to mirror `CLAUDE.md` (see Conventions)
6. `docs/dev/checklist-rows/<ID>.md` — add a row for any feature with runtime behavior that CI can't exercise (one file per row; see the table below)
7. **If a feature's RULE changed (not just its internals), grep the docs for the phrases the
   change falsified** — in the old rule's own words ("until scouted", the removed setting
   name), not the `§N`. Steps 1-6 cover the feature's own faces, not the other notes that
   merely mention it; the 2026-08-18 §3 rework left 8 stale claims behind, two on the wiki.
   `python tools/audit_stale_docs.py` checks every published file (README and `docs/wiki/`)
   against a table of removed features; CI runs it in `lint.yml` (job *Published docs*).
   **When you remove a feature, add its `Removed` row to that table in the same change.**
   Exit 1 = a published page still briefs a removed feature; exit 2 = a row's own pattern is
   inert. Audited in `docs/dev/design/retlab-doc-mass-notes.md`.

**Parallel PRs must not collide (STANDARD, 2026-09-29).** Several threads run at once, and
nearly every PR used to conflict in the same five places. Each now has a rule:

| Adding | Do this | Never |
|---|---|---|
| A checklist row | `python tools/claim_id.py row` prints the next free `B###`, reserved on GitHub, and writes its stub `docs/dev/checklist-rows/B###.md`; fill that file in | pick the number by reading the file, or add the row to the end of `retlab-ingame-pass-checklist.md` |
| A features-doc `§N` | `python tools/claim_id.py section` | the same |
| A changelog line | a new file `changelog.d/<slug>.feature.md` or `<slug>.fix.md` (see its README) | edit `changelog.md` |
| A What's New entry | a new file `resources/whatsnew/<date>-<slug>.yaml`, one entry | append to someone else's file |
| The outstanding count or summary table | nothing: `python tools/checklist_board.py` prints both from the row headings | write a count into the checklist |

The checklist, the features doc, the feature index, `CLAUDE.md`, `AGENTS.md` and
`changelog.md` are `merge=union` in `.gitattributes`: on a conflict in them, run
`git merge origin/main` in the worktree (or the app's sync) and git keeps both sides. Read
the merged spot anyway: a line both sides *changed* comes out twice, and a block one side
*deleted* comes back if the other side edited it. Duplicate row ids, `§` numbers and a
returned checklist summary fail a test. A branch that added its row to the end of the main
checklist moves it out with `python tools/checklist_rows.py move B###`. Rows from before
2026-09-29 stay in the main file; every reader reads both. A generated file (the feature
index) that comes out wrong is fixed by regenerating it.

---

## Project Docs

This file is the map. The territory is `docs/`. Read the relevant note **before** editing a
feature — each carries the design rationale, the flown-test findings, and the deferred work.

### Standing policies

- **Everything is upstreamable** (2026-07-19). "Clean and correct" is the bar; there is no
  permanent fork-only category. The one named exception is the Splash Damage tuning (see PINNED).
- **Upstream PR freeze** — see *Upstream PRs — standing rules* below.
- **Red Tide's feature lock was LIFTED 2026-08-03.** It takes new work like any other
  campaign. One exclusion survives as a separate call: the §71 F-4E pack stays un-preseeded.
- **Campaign ownership**: every fork-authored campaign has an owning design note and a CI lock.
- **A generated `.miz` is never hand-edited** where a build tool owns it. Edit the tool.

### Tracking docs — start here

| Doc | What it is |
|---|---|
| [retlab-features.md](docs/dev/retlab-features.md) | **The deep dive.** Every feature with file paths, gotchas, tests, deferred work. |
| [retlab-feature-index.md](docs/dev/retlab-feature-index.md) | Generated catalog of every feature with its plugin and `Settings` wiring. |
| [retlab-ingame-pass-checklist.md](docs/dev/retlab-ingame-pass-checklist.md) | Every "needs an in-game pass" item with a pass criterion and fail signature. Rows added from 2026-09-29 are one file each in `docs/dev/checklist-rows/`. Find a row: `grep -rn "^### B55 " docs/dev/retlab-ingame-pass-checklist.md docs/dev/checklist-rows`, then Read ~15 lines from there. Never search a bare row ID. |
| [flycards/WATCH.md](docs/dev/flycards/WATCH.md) | The standing opportunistic watch list — rows to adjudicate on any flight. |
| [flycards/LOCAL.md](docs/dev/flycards/LOCAL.md) | The rolling local test card for contrived conditions. |
| [retlab-early-systems-decision-ledger.md](docs/dev/retlab-early-systems-decision-ledger.md) | The 2026-07-18 deep-audit verdicts on the early-systems core, with self-play evidence. |
| [retlab-upstreaming-inventory.md](docs/dev/retlab-upstreaming-inventory.md) | The upstreaming queue, priority-ordered, with readiness marks, plus the **upstream issue ledger** (standing triage of upstream's open issues). |
| [retlab-upstream-pr-ledger.md](docs/dev/retlab-upstream-pr-ledger.md) | Every upstream PR we carved: status, review history, sync notes, DM exceptions to the freeze. |
| [retlab-community-contribution-roadmap.md](docs/dev/retlab-community-contribution-roadmap.md) | The long view: community-value × carve-difficulty across every feature. |
| [retlab-retribution-long-view.md](docs/dev/design/retlab-retribution-long-view.md) | Structural read of the engine (2026-08-17) and its seven seams. 1 and 4 are BUILT (§91, §90); 2 and 5 accepted, not started; 3 analysis only; 6 scoped in `retlab-coop-persistent-campaign-notes.md`; **7 (the enemy) DROPPED** — read [retlab-red-brain-phase0-notes.md](docs/dev/design/retlab-red-brain-phase0-notes.md) before proposing anything about red. |
| [retlab-campaign-architecture-notes.md](docs/dev/design/retlab-campaign-architecture-notes.md) | Direction note (2026-08-20, DM call): the one-substrate architecture, rungs R0–R7. Nothing built; each rung lands on its own call. |

### Campaign notes — `docs/dev/design/`

Read before touching a campaign's `.yaml`, `.miz` or build tool.

| Campaign | Note |
|---|---|
| Germany — Red Tide | `retlab-red-tide-campaign-notes.md` (+ `retlab-red-tide-supply-routes-notes.md`, `retlab-red-tide-c2-real-buildings-HANDOFF.md`) |
| Operation Baltic Fury | `retlab-baltic-fury-campaign-notes.md` |
| Marianas — Second Island Chain 2027 | `retlab-marianas-2027-campaign-notes.md` |
| Marianas — Operation Forager (1944) | `retlab-marianas-wwii-terrain-notes.md` (the terrain note owns it) |
| Syria — Anatolian Reach (2004) | `retlab-anatolian-reach-campaign-notes.md` — **Akrotiri stays support-only**; read the note first |
| Iraq — Umm al-Ma'arik (Desert Storm) | `retlab-desert-storm-campaign-notes.md` |
| Iraq — Operation Inherent Resolve | `retlab-inherent-resolve-campaign-notes.md` |
| Afghanistan — Enduring Resolve (COIN) | `retlab-coin-HANDOFF.md` — **start here for COIN** |
| Caucasus — Iron Gate | `retlab-iron-gate-campaign-notes.md` |
| Nevada — Red Flag 81-2 | `retlab-red-flag-81-campaign-notes.md` |
| Kola — Northern Flank 1985 | `retlab-northern-flank-campaign-notes.md` — Sweden and Finland hold nothing; Luostari has no jet stands |
| Vietnam set | `retlab-vietnam-retribution-HANDOFF.md`, `retlab-vietnam-retribution-notes.md`, `retlab-vietnam-ops-notes.md`, `retlab-vietnam-red-tempo-notes.md` |
| Iraq map 2.9.28 content | `retlab-iraq-map-2928-notes.md` — authoring plan, not yet built |

### System notes — `docs/dev/design/`

One line each; the status is the note's own. Read the note, not this line, before editing.

- **IADS / air defense** — `retlab-skynet-return-notes.md` (**start here**: Skynet is the
  engine again since 2026-09-12; MANTIS and the MIST shim are gone),
  `retlab-sam-site-realism-notes.md`, `retlab-air-defense-planning-notes.md`,
  `retlab-qra-player-manning-notes.md`, `retlab-sam-magazines-notes.md` (scoping only),
  `retlab-iran-iads-deployment-notes.md` (research: where Iran's SAMs sit, map by map)
- **EW / ISR / comms** — `retlab-c130-ew-isr-notes.md`, `retlab-gps-jamming-notes.md`,
  `retlab-iads-c2-consequences-notes.md`
- **Recon** — `retlab-recon-role-scoping-notes.md` (candidate A built 2026-08-18; B and C scoping)
- **CSAR** — `retlab-csar-notes.md` (the one CSAR doc)
- **COIN** — `retlab-coin-insurgent-replenishment-notes.md`, `retlab-coin-reinfiltration-notes.md`
- **Naval** — `retlab-cruise-missile-raids-notes.md`, `retlab-naval-magazines-notes.md`,
  `retlab-carrier-deck-decor-notes.md`
- **Ground / frontline** — `retlab-tic-dynamic-fronts-notes.md`,
  `retlab-pr823-frontline-merge-notes.md` (read before adopting upstream #823),
  `retlab-airlift-capacity-notes.md` (built 2026-08-26; **`cabin_size` is CTLD seats, not
  airlift**), `retlab-het-convoy-notes.md` (scoping only),
  `retlab-observer-gated-artillery-notes.md` (scoping only),
  `retlab-front-movement-arrows-notes.md` (built 2026-09-23, row B139)
- **Tankers** — `retlab-tanker-box-notes.md` (per-flight orbit speed, the 40 NM racetrack
  every theater tanker flies, and why the four-corner box was removed 2026-10-09; rows
  B152/B206)
- **AI behaviour** — `retlab-ai-threat-reaction-notes.md` (§94; the `aiReactionExempt`
  protocol any plugin setting reaction-on-threat must use)
- **Iran air defense (§105)** — `retlab-iran-air-defense-pack-notes.md` (the unit-id contract
  and numbers), `retlab-iran-air-defense-pack-HANDOFF.md` (the private pack's local build)
- **Neutral factions** — `retlab-neutral-border-defense-notes.md` (§98; why a true neutral
  cannot fire, and the DM-locked rules), `retlab-national-postures-notes.md` (the posture
  table; consent moved to airbases 2026-08-26; the measured country-per-map table)
- **Strike targets / BDA** — `retlab-scenery-kill-tracking-notes.md` (position matcher adopted
  from upstream #957 on 2026-08-30; row B63 verified in test 33)
- **Package route / waypoint editing** — `retlab-package-route-notes.md` (§106; routes are
  edited on the map, never by typed coordinates; rows B150/B151)
- **Planning / doctrine** — `retlab-hq-priority-targets-notes.md` (§103),
  `retlab-planner-doctrine-mining-notes.md` (how we teach the scripted planner; read its
  guardrails first), `retlab-llm-opfor-notes.md` (§109: the outside AI that reads red's turn;
  the 2026-10-09 DM call that reversed "no LLM runs in this fork"), `retlab-falcon-bms-campaign-notes.md` (study),
  `retlab-region-priorities-notes.md` (§93), `retlab-substrate-inventory-notes.md` (R0, done),
  `retlab-substrate-HANDOFF.md` (start here to continue the substrate work),
  `retlab-aircraft-task-rebalance-rubric.md`, `retlab-victory-conditions-notes.md`,
  `retlab-single-player-loop-notes.md`, `retlab-autoplanner-upstream-divergence-audit.md`
  (the full fork-vs-upstream planner diff; read before reverting or carving planner behavior),
  `retlab-cruise-mach-notes.md` (built 2026-09-01; only the F/A-18C is authored),
  `retlab-bullseye-notes.md` (§95), `retlab-flight-report-cards-notes.md` (§108, row B158),
  `retlab-coop-persistent-campaign-notes.md` (scoped, not built)
- **Cockpit / data** — `retlab-dtc-cartridge-notes.md`, `retlab-weapon-dates-proposal.md`,
  `retlab-datalink-era-notes.md` (`DatalinkPolicy`, built 2026-08-16),
  `retlab-dynamic-spawn-templates-notes.md` (§101, row B125), `retlab-my-aircraft-notes.md`
  (§102, rows B135/B136), `retlab-startup-times-notes.md` (read before adding a
  `startup_minutes:` value), `retlab-loadout-integrity-audit-notes.md`
- **Terrain / maps / weather** — `retlab-marianas-wwii-terrain-notes.md` (built 2026-08-22;
  read its traps before exporting another terrain), `retlab-atmosx-live-weather-notes.md`
  (adopted from upstream #927)
- **Framework / tooling** — `retlab-moose-ops-opportunity-map.md`,
  `retlab-lua-plugin-harness-notes.md`, `retlab-splash-damage-notes.md` (why the Splash
  Damage build is pinned)
- **Structure / debt** — `retlab-doc-mass-notes.md` (the 2026-08-19 features-doc trim, and
  **how to replace a section without destroying its neighbours**)
- **Process** — `retlab-verification-cadence-notes.md` (partly built: WATCH, LOCAL, the
  session hook), `retlab-sim-thread-freeze-notes.md` (**read before chasing a stutter**; test
  in model time, never wall time), `retlab-dcs-update-2026-08-26-notes.md` (that patch
  triaged, verified against the install the same day), `retlab-dcs-log-noise-notes.md` (read
  before triaging a `dcs.log`), `retlab-dcs-olympus-notes.md`, `retlab-ui-redesign-directions.md`
  (+ `-mockups.html`), `retlab-ui-consistency-audit-notes.md` (the UI text house style),
  `retlab-campaign-doc-ideas-harvest.md`
- **Other forks and projects we watch** — `retlab-juanjux-fork-watch-notes.md`,
  `retlab-liberation-watch-notes.md`, `retlab-mist-author-repos-notes.md` (licence-gated),
  `retlab-fincenturion-dist-notes.md` (study only; read, never vendor)

### Superseded, draft or historical

Kept for reading old notes and saves; **do not author against them**.

`retlab-ewrs-retirement-decision.md` · `retlab-dismounts-decision.md` ·
`retlab-ctld-mantis-style-port-scope.md` · `retlab-mission-planning-wiki-rework.md` ·
`retlab-scenery-import-notes.md` · `turnless.md` · `retlab-wing-growth-notes.md` (§82 removed) ·
`retlab-framework-consolidation-notes.md` and `retlab-moose-longview.md` (both written while
MIST was retired) · `retlab-tanker-war-campaign-notes.md` (campaign removed)

### Deleted design notes

18 notes on removed features were deleted 2026-08-20; they are at
`git show 5db34150f:docs/dev/design/<name>` and keep the pre-rebrand `414th-` prefix.
**Do not keep a note for a removed feature**: record the removal in the features doc §N and
delete the note, after lifting any **constraint learned from a flown test** into the
hard-constraints list or a surviving note. The deleted debt register is at
`git show bb8d019c6:docs/dev/414th-feature-debt-register.md`.

### Other

- [README.upstream.md](README.upstream.md) — unmodified upstream README (setup, dependencies).
- [references/manuals/](references/manuals/) — official DCS manuals for 11 aircraft modules
  plus the Supercarrier guide. The PDFs are gitignored; read the folder's tracked `INDEX.md`,
  then extract only that range with `pdftotext -f N -l M <pdf> -` (the Read tool can't open
  them here). Use them for procedure and systems, **not** loadouts, weapon dates or unit stats.
  The `dcs-aircraft-manuals` skill wraps this.
- [docs/wiki/](docs/wiki/) — the player and contributor wiki, mirrored to the GitHub wiki by
  `wiki-sync.yml` on every push to `main`. **Edit pages here, never in the wiki UI.** Also
  carries the adopted upstream dev-process standards, each with **RetLab:** delta notes.
- `AGENTS.md` mirrors this file — see **Conventions**.

## Tech Stack

| Layer | Choice |
|---|---|
| Campaign engine | Python 3.11 (`game/`). Library catalog, reference only: https://github.com/vinta/awesome-python |
| UI | PyQt (`qt_ui/`) + React/Leaflet client (`client/`) — client NOT type-checked in CI |
| Mission scripting | **Lua 5.1** sandbox plugins (`resources/plugins/`) — no `os`/`io`, no `goto`, definition order matters |
| In-mission framework | **MOOSE** (bundled `Moose.lua`; some plugins vendor classes verbatim) is the standard. **MIST is upstream's `mist_4_5_126.lua`** again since 2026-09-12, and `base/plugin.json` is upstream's work-order list plus the fork's `sortie_recorder.lua`; a merged upstream Lua file that calls `mist.*` needs no shim work. MOOSE API docs: https://flightcontrol-master.github.io/MOOSE_DOCS_DEVELOP/Documentation/index.html |
| Units / mission format | pydcs; CurrentHill mod packs in `pydcs_extensions/` |
| CI gates | Black + mypy + pytest + the published-docs audit + the Lua 5.1 syntax gate (all blocking), plus advisory luacheck and dead-code report — see `docs/dev/CLAUDE-ci.md` |
| Release | PyInstaller → rolling `latest` pre-release on GitHub |

---

## Key Architecture Patterns

**Planner / Lua split.** Python plans and spawns the mission (flight plans, ROE, templates);
runtime behavior (EW, ISR, frontline firefights) is driven by the Lua
plugins. When a feature has both, the Python side sets up and the Lua side executes — don't
move runtime logic into the planner or vice versa.

**Plugin script injection (the uniform late-init pass).** Most RetLab plugins are normal
work-order plugins. TIC additionally needs its main script loaded **after**
every plugin's config table exists (its init reads `dcsRetribution.plugins.<name>` / MOOSE
at file scope). It is a `LuaPlugin` subclass (`game/plugins/tic.py`, registered in
`manager.py`'s `_PLUGIN_CLASSES`; `MooseAtis` is registered there too, but only to inject the
current map's sound files) declaring `late_init_files()` / `late_init_preamble()` /
`should_late_init()`; `inject_plugins()` runs a **second pass** that calls
`inject_late_init()` after the normal config pass. A missing or renamed init file is caught
by `game/plugins/tests/test_late_init.py`.

**Viewer-aware visibility layer (recon fog).** AI planning and threat math always use ground
truth (`viewer=None`); only the human (BLUE) map/UI are fogged. **One question, asked in one
place**: `TheaterGroundObject.visibility_for(viewer)` returns HIDDEN / UNKNOWN / KNOWN, and
`known_for` + `hidden_on_player_map` are its two leaves. `known_for` gates composition and
threat/detection rings (`recon_intel_fog`); `hidden_on_player_map` fully hides enemy command
posts (`scar_command_post_intel`) and §50's ambush teams. Nothing else is viewer-aware except
`standard_identity_for` (COIN's suspect-until-engaged symbol).
**A site is revealed by engaging it — ordnance on it, or any ground-attack sortie that reaches
it — and is then known completely and permanently, damage included.** Two other reveals:
fixed SAM sites (`is_fixed_sam_site`) are always known, and a captured enemy commander
reveals every command post. Recon/TARPS reveals nothing except a hidden command post within
3 NM of its target (`reveal_scouted_command_posts`). There is no BDA damage lag:
`alive`/`is_dead`/`dead_units`/`max_threat_range`/… are plain truth. Do **not** reintroduce a
viewer parameter on those, or the old `_for_player`/`_for` method twins.
**Anything that picks targets FOR blue automatically must gate on the fog** — auto raids
(§63), the carrier strike (§44), C2 decapitation (§52), HQ priorities (§103), any future fire
mission. Use `fogofwar.hidden_from(Player.BLUE, tgo)`, never a bare `hidden_on_player_map`: it
wraps `fog_intact()`, so a host who ticked the reveal overview cannot get a different target
than one who did not. Red is never fogged. Keep the §50 `map_hidden` skip separate — it
applies to both sides.
A runtime **overview toggle** (`game/theater/fogofwar.py`, transient/never-pickled)
short-circuits both fog leaves to ground truth, so the whole render path and intel dialogs
un-fog with **no** server-model changes. It is a checkbox in `MapLayersControl` (§18), driven
by a state `useEffect` (not a Leaflet add/remove layer — unmount doesn't reliably fire
`remove`) that `PUT`s `/fog-of-war/reveal` then re-pulls `/game`. (See features doc §3.)

**Save migration.** Removed/renamed enum *values* migrate in **one place**:
`FlightType._missing_` (`game/ato/flighttype.py`) maps legacy persisted strings to live
members via the `_LEGACY_FLIGHT_TYPE_VALUES` table. The unpickler (`persistency.py`
`_handle_flight_type`) calls `FlightType(value)`, which routes through `_missing_`, so it
carries **no** parallel remap table — only unknown-value tolerance (degrade to BARCAP).
Other persisted state (e.g. fog) migrates in each class's `__setstate__`. When you rename a
persisted enum value, add the entry to `_LEGACY_FLIGHT_TYPE_VALUES` only.

**Lua plugin discipline.** Lua 5.1 only, vanilla DCS units only, define functions before
first use. The *Lua 5.1 syntax* job in `lint.yml` runs `luac5.1 -p` over every
`resources/plugins/**/*.lua` (parse-time errors). The **headless Lua plugin harness**
(`tests/lua/`, `retlab-lua-plugin-harness-notes.md`) runs the real plugin scripts on Lua 5.1
via `lupa` against a faked DCS sandbox inside the normal pytest run, and covers most plugins.
It catches "the script errors at runtime and the feature silently never starts" and pins
safety invariants; it models no DCS AI or physics, so real behavior still needs an in-game pass.

**Finding things in the big files.**
- `game/settings/`: a field lives in `fields/<page>.py` — `grep -rn "^    <field>:" game/settings/fields`; by UI label `grep -rn -B1 '"<Label>' game/settings/fields` (the label is on the line after the field). Dialog layout is `layout.py`, old-save rewrites `migration.py`.
- `game/missiongenerator/kneeboard/` (a package since #1066): one module per page family — `grep -rn "^class .*Page" game/missiongenerator/kneeboard` first.

---

## Features at a Glance

One line each. **Full internals — file paths, gotchas, tests, deferred work, flown-test findings
— are in [docs/dev/retlab-features.md](docs/dev/retlab-features.md) under the matching §N.** Read
that section before editing a feature; this list is an index, not a spec.
Find §N: `grep -nE "^## (§)?57[. ]"` — §1–18 are mostly headed `## N.`, the rest `## §N —`.

The generated catalog is [docs/dev/retlab-feature-index.md](docs/dev/retlab-feature-index.md); the
source of truth is the registry `game/retlab/features.py` (regenerate with
`python -m game.retlab.features`). **Register every new feature there** or CI fails.
Claim its `§N` first with `python tools/claim_id.py section`.

### Hard constraints — established by flown tests, do not undo

These cost a mission or a crash to learn. Each is recorded in full in the features doc or the
linked design note.

- **Never restore the per-base backstop EWR** (§1). DCS has no non-colliding ground unit; the
  mast sat on taxiways and broke AI taxi routing. Any authored ground object inside a runway
  strip or apron does the same (test 35: upstream's own Incirlik EWR marker). New Game logs
  `Airfield clearance:` for every ground object inside a runway band (300 m, 1.6 km) or 80 m
  of a stand (`game/theater/airfieldclearance.py`); it warns, it never moves a marker.
- **Never restore the generic `ewrj` fighter-pod jammer** (§2). Superseded by the C-130J.
- **The C-130J cues; it never lases or designates.** It carries no targeting sensor in DCS.
  Retribution has no FAC(A) task type; §38 does marking through Vietnam Ops.
- **Never unify §77 escort jamming with the C-130's standoff model.** §77 strengthens as the
  jammer closes; the C-130's burn-through weakens. Both are intentional and opposite.
- **Never add a land-attack weapon family to the §81 anti-ship pattern list.** §63 and §81 stay
  correct only because their weapon sets are disjoint.
- **GPS jamming (§86): at most 3 sites per campaign, non-overlapping.** Bubbles are large and
  invisible on the map, and effects do not stack.
- **A mover's DCS group needs a 2-waypoint route** — current position, then destination. A
  single destination waypoint reads as "already there" and the group never drives.
- **One undrivable member pins a whole group.** A route push moves a DCS group as a unit, so a
  static emplacement in it yields no movement and a ground-AI levelling storm. This is why
  §85's missile-battery support section is trucks only.
- **A tanker track is DCS's own racetrack orbit, never a waypoint route.** A KC-135 banks
  45 degrees alone, 25 with a jet joined up and 15 with one on the boom; on a 30 x 15 NM
  route box it never flew level in contact (2026-10-09). `retlab-tanker-box-notes.md`.
- **Movers must last 90 minutes.** Any player-interactable mover is paced so an intercept is
  still possible late in a mission.
- **Never spawn phantom units.** Every scripted force is a real, tracked unit whose loss records
  natively. Applies to §35, §37, §50.
- **Never script explosions on an airfield.** `trigger.action.explosion` inside a field's area
  puts it into DCS's under-attack state and every AI fixed-wing launch there is held until it
  clears; a recurring barrage never clears it (§36, removed). A one-off strike is not this.
- **A plugin toggle is a second gate.** An unticked plugin silently kills its setting — campaigns
  must preseed both. A `skipUI` plugin has no checkbox and is always on (`LuaPlugin.enabled`):
  `base`, `intercept`, `opscsar`, `vietnamops`.

### Live features

1. **QRA intercept reserve** — per-squadron alert reserve feeding the Moose `AI_A2A_DISPATCHER`, with player-manned cold alert, a scramble cue, and forward-defense border zones.
2. **JAMMING flight type** — the C-130J as an EC-130H/RC-130H EW + ISR platform (`c130j` plugin).
3. **Recon intel fog** — an enemy site's composition stays hidden until you engage it; once engaged it is known completely and permanently. Fixed SAM sites are always known. Recon's only job is finding the hidden enemy command posts.
4. **UI transparency** — target intel panel, mission-impact debrief, package context bar.
5. **Player target location precision** — `Approximate` mode offsets steerpoints and hides exact coords.
6. **Air-defense planning rework** — overlapping BARCAP waves, the first one ASAP along with every tanker and AWACS; no BARCAP over an LHA within 80 NM of a friendly carrier. The geometry half was reverted to upstream 2026-08-09.
7. **Auto-hide mobile SAMs on MFD** — SHORAD/AAA/MANPAD off datalink; MERAD/LORAD stay visible for SEAD.
8. **Robustness, crash fixes and refuelling** — helo CFIT, carrier-recovery stagger, convoy runway spawns, support-flight radio collisions, locked speed/time route rejection; per-flight Refuel before the push and Refuel before station.
9. **TIC — Troops In Contact** — scripted frontline firefights with per-stance movement and ambient fire.
10. **CurrentHill Iran assets pack** — Shahed-136, IRGCN FAC, `[CH] Iran 2020` faction.
14. **Plugin Options UI** — `descriptionInUI` field plus label and default polish.
16. **Settings QOL audit** — dead-field cleanup and the `AiRadioBehavior` enum consolidation.
17. **Auto-planner target unpredictability** — opt-in per-side reordering of opportunistic offensive targets only.
18. **Fog-of-war overview toggle** — transient reveal, never persisted, and fenced out of generated missions.
19. **Unified map layers panel** — one grouped control with preset views; air-defence rows filter the master.
22. **Kneeboard space-utilisation + custom import** — per-campaign imported kneeboard images.
23. **Per-squadron DCS country** — nation-specific voiceovers and pilot names, pinnable per squadron.
24. **Date-gated aircraft properties** — era-gated payload-editor options under `restrict_props_by_date`.
26. **Off-mission combat fidelity** — capability-weighted auto-resolution plus the PLAYER_AT_IP fast-forward fix.
27. **Shared-airframe kneeboard index** — one index page when several client flights share a type.
28. **Settings IA reorg + difficulty presets** — metadata-driven layout, difficulty presets, search filter, and the RetLab Features page.
29. **Campaign SITREP** — a last-turn digest on its own kneeboard page, the web ribbon, and the Qt debrief.
32. **Arc Light** — heavy bombers walk a bomb carpet across a Strike target *(Vietnam Ops)*.
33. **AAA flak gauntlet** — barrage flak that tightens against predictable run-ins *(Vietnam Ops)*.
34. **Naval gunfire support** — call-for-fire and automatic coastal bombardment *(Vietnam Ops)*.
35. **Convoy interdiction** — real tracked trail convoys hunted via Armed Recon *(Vietnam Ops)*.
37. **Super Gaggle** — real squadron helos resupplying a cut-off outpost *(Vietnam Ops)*.
38. **FAC(A) willie-pete marking** — an OV-10 marks the largest enemy concentration *(Vietnam Ops)*.
39. **Snake and nape** — detonation-anchored napalm fire from a low fast release *(Vietnam Ops)*.
41. **High Digit SAMs Ultimate Compilation** — S-400, S-300V4, SAMP/T, Pantsir-SM, period EWRs.
42. **Local DCS chart base layers** — locally installed XYZ tile pyramids as extra base maps.
43. **Per-aircraft flight defaults** — saved fuel and cockpit properties per airframe.
44. **Long-range carrier ops** — a deterministic package off a standoff boat, routed to its own tanker.
45. **Support-package F10 markers** — tanker and AEW&C orbits and CAP stations drawn on the F10 map, with callsign, freq and TACAN.
47. **Continuous campaign clock & weather** — one marched clock with weather evolving from the previous turn.
50. **Convoy ambush + ambient supply convoys** — untelegraphed ambush teams on friendly roads, authored as native DCS triggers.
52. **Command-center decapitation** — a headless HQ picks targets worse and frags fewer offensive packages.
56. **Strikeable motorpool depots** — the reserve armor pool made bombable, 1:1 with no economy.
58. **Mission-start briefing popup** — per-pilot slot-in cards with a beep and the taxi call.
61. **Host red-interceptor scramble** — an F10 bandit spawner for a quiet event.
62. **Squadron-sequenced modexes** — per-squadron number blocks for Hornets, a CAG bird and line jets for Tomcats; the Payload tab can pin a flight's number.
63. **Ship-launched cruise missile raids** — finite no-rearm magazines, auto raids and an F10 call-for-fire, with a defender launch wake.
64. **Carrier deck spawn policy** — AI carrier flights spawn clear of the six-pack; player carrier flights always spawn at mission start, so their MP slots work.
65. **Curated carrier comms** — per-hull TACAN, ident, ICLS, Link 4 and ATC feeding the CV Operations Data page.
66. **Generated-mission archive** — a dated copy of every generation, in a folder DCS lists.
67. **Weather-aware auto-planning** — rain grounds auto-recon; storms demote low-level attack.
68. **Adaptive procurement** — price-weighted buys and optional SAM site repair.
69. **SEAD-before-strike coordination** — strikes retimed behind the suppressor servicing their target.
71. **Expanded F-4E Weapons Pack** — AGM-78 Weasel fits gated on live pylon legality.
72. **Carrier deck decorations** — island-street and LSO dressing, clear of every parking spot and standing for the whole mission.
73. **Per-airframe default loadout for a task** — pin a fit for an airframe and task across campaigns.
74. **Native DTC data pre-population** — auto-loading cartridges for the Hornet, Viper, F-14B(U) and Apache, with a per-flight DTC tab.
75. **Custom victory conditions** — authored win/lose blocks plus generic domination and attrition endings.
76. **CTLD paratroopers** — fixed-wing Air Assault by paradrop, player and AI.
77. **Escort jamming** — EA-18G and EA-6B only; non-stacking spoof bubbles and SAM weapons-hold pulses.
78. **Sea-supply convoys + coastal anti-ship** — proportional convoy losses and batteries that actually engage.
80. **Mixed-hull ship groups** — task groups instead of copies of one hull, family-bounded.
81. **Cross-turn naval magazines** — staggered weapons-free release and finite anti-ship stock, released on attack.
83. **SP Pilot Mode** — accept-and-fly-next, an aircraft-first sortie board, and a pre-turn reasons-to-continue brief.
85. **SAM/missile battery support sections** — refuellers, power and transload in the faction's own kit.
86. **GPS jamming** — satellite-guided weapons released inside the bubble land long.
87. **Naval station-keeping racetracks** — anchored ovals so ships hold station under way.
88. **Angled-deck carrier recovery heading** — the boat steams for 25 kt down the angled deck, not the bow.
90. **Front-line model** — reinforcement follows the supply lines, attacking costs more than defending, the line's position counts the forces actually present, terrain slows the advance, and the front bulges instead of running straight. The map arrows last turn's movement on each front.
91. **Per-flight sortie records** — the mission reports back what each flight did: track, time airborne, fuel, shots and hits, not just which units died.
92. **What's New** — a toolbar window listing the recent player-visible changes, each with what to look for in the next mission.
93. **Region priorities** — per-control-point BLUE planning emphasis: emphasized regions rank closer, deprioritized farther, ignored left to manual packages. A weight, never a fence.
94. **Smart threat reaction** — only the flight a missile is actually guiding on goes defensive; everything else holds formation and uses countermeasures.
95. **Pinned bullseye** — one bullseye for the campaign instead of a new one every turn, never anchored on a ship or an off-map spawn; the kneeboard names the place it sits on and flags the rare turn it moves.
96. **Player career logbook** — a permanent record per pilot: sorties, combat sorties, hours airborne, air/ground/naval kills, ejections and rank, folded from what the mission actually recorded. Ranks are data, not code. A record, never a reward — nothing here unlocks an aircraft or gates a mission. Awards were removed 2026-09-22.
97. **Lifetime pilot profiles** — your own flying kept across every campaign, not just the current one: totals, a breakdown per aircraft, and the individual flights. Identified by DCS player name, so it needs no setup and a multiplayer host records every pilot who flew. Stored outside the save, which is what lets it outlive a campaign.
98. **Neutral-faction border defense** — every nation on the map is drawn with its real border, the map's own nation included: alignment derived from who holds the airfields inside it, counted per country (both sides holding it = contested grey, claimed by neither QRA; a country in the war is outline-only; red-aligned airspace joins §1's QRA accept zones), and a country not in the war defends (overflight is derived from the same airbases: you may cross what you fly from, and what both sides fly from) — it stands live SAM batteries inside its border from mission start, in two tiers -- the era picks legacy (SA-2/3/5) or modern (SA-10/11, plus Hawk/Patriot/Rapier for the western-equipped list) and the country's room picks the rung, the top band being the same in both eras -- and counted off it too (~1 per 200 NM of war-facing frontier, capped at 6, map clip and far-from-the-war stretches unmanned), each placed well short of what its missile claims, so the frontier sits inside the envelope with margin rather than on its edge, visible before you cross, and hailing you on entry; press, and the WHOLE country turns hostile in place on your enemy's coalition and engages. Both sides violating one country gets a second set. Countries DCS does not model (Turkmenistan, Uzbekistan, Tajikistan, Armenia, Azerbaijan) borrow a neighbour's units rather than being dropped. Players only; AI is never engaged, unless the `engageAi` plugin option is ticked -- a testing override, default off, that holds AI to the same ladder. The fighter patrol was dropped 2026-09-07 -- scope is the SAM.
99. **Sandy rescue escort** — an armed escort that works the ground around a downed pilot while the helicopter comes in: a track centred on the survivor, flown by the A-10 and the Apache. Hand-fragged only — the auto-planner never adds one.
100. **King on-scene commander** — the player-flown C-130J King finds the survivor by DF cuts on the beacon (two cuts far enough apart make a fix; inside pod range with line of sight it snaps exact), sweeps the ground around the fix for threats reported as a class and a rough position, and passes the picture — text and map marks — to the player-crewed Sandy and helicopter. Cues only: it never lases, and nothing is pushed onto an AI flight.
101. **Dynamic spawn templates** — a pilot who takes a DCS dynamic slot no longer gets a blank jet: at each base, one player flight of each type is marked as DCS's Dyn.SPAWN Template and the warehouse link written, so the dynamic jet is built from that flight (loadout, properties and livery for certain; route and radio presets are decided in native code and are what row B125 flies). Client flights only, no clone, and the fragged slot still flies as itself. Types with no player flight at the base stay blank. Off with `dynamic_slots`, and its own toggle beneath it.
102. **My aircraft, saved points and the DTC options** — one window for the seat you are flying: saved points (waypoint, IP, target, hold, orbit) and drawings, the loadout and the data cartridge. Points and drawings reach the Hornet, Viper, F-14B(U), Apache and A-10 where each cockpit has a place, and a kneeboard page with the cockpit's numbers. The DTC tab shows only what the jet's cartridge carries, with load-at-spawn or by-hand, waypoint types to leave out, and SAM rings near the route. Window and points ported from juanjux/dcs-escalation.
103. **HQ priority targets** — what losing each enemy target costs the enemy, in that kind of target's own measure (income, front-line vehicles, offensive packages, equipment price), ranked within its kind. A Why it matters line on the target panel always; a blue-only planner weight, gentler than §93, when on. No prize. The objective half of juanjux's High Command.
105. **RetLab Iran Air Defense Pack** — Retribution support for a RetLab-authored mod carrying 3rd Khordad (MERAD, Buk-like) and Bavar-373 (LORAD, S-300-like; one launcher, firing the Sayyad-4B, since 2026-09-30: the STR guides every launcher, as on an S-300 site), the Matla ul-Fajr EWR and the Rasool comms shelter as the Iranian IADS network node, with Skynet entries and presets in `[CH] Iran 2020` and `[CH] Iran 2025`, plus the Sejjil-2, Emad, Kheibar, Fattah-2 and Shahed 238 missile launchers (which replaced the third-party ones 2026-09-29). The mod is its own private pack, flown in tests 41-46; the 3rd Khordad kills, the Sayyads have not yet reached a target.
106. **Package route and map route editing** — routes are edited on the map: drag a point, double-click the selected route to add one, right-click to delete. The join-to-IP and target-to-split legs every formation flight in a package flies together are the package's, so an edit there lands on every flight (from any flight of the package), and a flight added later flies the same route; the package window's Package route button lists it. Insert NAV point in a flight's Waypoints tab finds a leg beside any waypoint, and on the package route asks whether the point is for the whole package.
107. **Briefing screen picture** — the picture DCS shows when a generated mission loads is RetLab's own; drop `briefing.png` or `briefing.jpg` into `Saved Games\DCS\Retribution` to use yours. No setting.
108. **Flight report cards** — the debrief grades every blue flight that flew, yours first: timing at the TOT waypoint, the package target, kills, shots and hits, losses and your landing fuel against the jet's reserve, from §91's records. Unsat to Above average, with the faults listed. A record, never a reward. No setting.
90. **Front-line model** — reinforcement follows supply lines, attacking costs more than defending, position counts the forces present, terrain slows the advance, and the map arrows last turn's movement.
91. **Per-flight sortie records** — the mission reports what each flight did: track, time airborne, fuel, shots and hits.
92. **What's New** — a toolbar window listing recent player-visible changes, each with what to look for in the next mission.
93. **Region priorities** — per-control-point BLUE planning emphasis. A weight, never a fence.
94. **Smart threat reaction** — only the flight a missile is guiding on goes defensive; everything else holds formation and uses countermeasures.
95. **Pinned bullseye** — one bullseye for the campaign, never on a ship or an off-map spawn; the kneeboard names the place.
96. **Player career logbook** — a permanent per-pilot record of sorties, hours, kills, ejections and rank, from what the mission recorded. A record, never a reward.
97. **Lifetime pilot profiles** — your flying kept across every campaign, keyed by DCS player name and stored outside the save.
98. **Neutral-faction border defense** — every nation drawn with its real border; a country not in the war stands live SAMs inside it, hails a player who crosses, and turns hostile on the enemy's coalition if pressed. Alignment comes from who holds its airfields. Players only unless the `engageAi` testing option is ticked.
99. **Sandy rescue escort** — an armed escort working the ground around a downed pilot, flown by the A-10 and Apache. Hand-fragged only.
100. **King on-scene commander** — the player C-130J King fixes the survivor by DF cuts, sweeps for threats and passes the picture to the player Sandy and helicopter. Cues only.
101. **Dynamic spawn templates** — one player flight per base and type is marked as DCS's Dyn.SPAWN Template, so a dynamic-slot jet is built from it instead of blank.
102. **My aircraft, saved points and the DTC options** — one window for your seat: saved points and drawings (Hornet, Viper, F-14B(U), Apache, A-10), the loadout and the DTC tab. Ported from juanjux/dcs-escalation.
103. **HQ priority targets** — what losing each enemy target costs the enemy, ranked within its kind; a panel line always, a blue-only planner weight when on. No prize.
104. **Runway queue at busy fields** — taxi allowance grows 45 s per jet ahead, and the mission starts up to 30 minutes early when a flight needs it; ASAP tankers, AWACS and the first CAP launch with it. Always on, no setting.
105. **RetLab Iran Air Defense Pack** — support for RetLab's private mod: 3rd Khordad, Bavar-373 (Sayyad-4B), the Matla ul-Fajr EWR, the Rasool IADS node and five missile launchers, in `[CH] Iran 2020` and `[CH] Iran 2025`. Flown in tests 41-53; both SAMs have kills.
106. **Package route and map route editing** — routes are edited on the map (drag, double-click to add, right-click to delete); the join-to-IP and target-to-split legs belong to the package, so an edit there lands on every flight.
107. **Briefing screen picture** — RetLab's own load-screen picture; drop `briefing.png` or `briefing.jpg` into `Saved Games\DCS\Retribution` to use yours.
108. **Flight report cards** — the debrief grades every blue flight that flew, yours first, from §91's records. A record, never a reward.
109. **Outside AI reads red's turn** — a REST API under `/retribution-ai/*` for an AI on the same PC: it reports what looks wrong in red's plan, and with the Outside AI plans red setting ticked (Campaign Management; also on the new game wizard's Campaign options page) it plans red's packages, TOTs, stances and buying, starting from the plan the scripted planner still makes every turn. Developer tools > Copy AI connect link. Red only; blue's ATO is never served. Ported from juanjux/dcs-escalation; loadouts, waypoints, transfers, ships, repairs and MCP are staged after it.

### Retired, removed or shelved — do not restore

Kept numbered so old notes and saves stay readable. Details and rationale in the features doc.

| § | Feature | Status |
|---|---|---|
| 11 | Native DCS DTC cartridge export (v1) | Retired 2026-06-26 — superseded by §74 |
| 12 | Recon engine (TARPS + drone BDA) | Removed 2026-08-20 — the §3 rework left its captures with no consumer |
| 13 | Flight Control ATC | Retired 2026-06-26 |
| 20 | Drop-spawn map unit placement | Removed 2026-08-02 |
| 15 | SCAR — the fork's first RESCAP "Sandy" escort | Removed 2026-08-07 — §99 is the live Sandy |
| 21 | Combat SAR (fork implementation) | Removed 2026-08-07 — replaced by upstream #929 (an open PR), re-adopted by hand phase by phase; read `retlab-csar-notes.md` before touching the hover height. The King is hand-fragged only |
| 25 | Compact 3–4 page kneeboard deck | Retired 2026-07-05 |
| 30 | Dedicated kneeboard cover page | Retired 2026-07-13 — new info folds into a stock page |
| 31 | One-page Brief Sheet | Retired 2026-07-13 — BLUF and code words survived |
| 40 | Campaign phases, ROE zones, target release | Removed 2026-07-21 |
| 46 | Route-aware fuel-tank planning (fuel-first) | Reverted 2026-08-09 — nothing fits tanks; the external-fuel accounting helpers survive for the readouts. Tanker tasking has fork additions since (§6, §8) |
| 48 | Commitment ceiling and the political-will economy | Removed 2026-07-21 |
| 49 | Mobile missile relocation (the SCUD hunt) | Removed 2026-08-29 — never relocated a site in three flown attempts |
| 51 | Enemy comms jamming | Removed 2026-09-07 — audio pressure that never changed the force model |
| 70 | COMINT collection (and the red comms net) | Removed 2026-09-07 |
| 36 | Airbase harassment (and the frontline artillery mode) | Removed 2026-09-16 — grounded AI launches; see the airfield-explosion constraint |
| 89 | Living battlespace | Removed 2026-09-07 |
| 53 | War economy | Removed 2026-07-21 |
| 54 | Munitions availability | Removed 2026-07-21 |
| 55 | Red Intent adaptive posture | Removed 2026-07-21 |
| 57 | Air-droppable minefields | Removed 2026-09-07 |
| 59 | Ground AI sleep | Removed 2026-09-23 — never observed doing its job in a flown test |
| 60 | SAM guidance-radar redundancy (two track radars per site) | Removed 2026-09-29 — every SAM site is back to one guidance radar |
| 79 | Decoy suspected-activity zones | Removed 2026-08-18 |
| 82 | The Wing Grows (scheduled squadron arrivals) | Removed 2026-08-16 |
| 84 | Old-stock loadout attrition | Removed 2026-08-06 |

Also removed: the blank-start campaign maker (2026-08-02), the SOF capture economy (2026-07-01),
and the MOOSE MANTIS IADS bridge with its MIST shim (removed 2026-09-12).

## Repo & Branch Layout

- This repo (`BradySox/RetLab`) `main` is the consolidated, most-up-to-date RetLab build.
- Upstream is `dcs-retribution/dcs-retribution`; RetLab's PR fork is `BradySox/dcs-retribution`.

### Forks and projects we watch

- **DCS Liberation** (`dcs-liberation/dcs_liberation`, branch `develop`) — the grandparent
  project, still developed. A second upstream we take from and never carve to. Skim its
  release notes when one drops, `[Data]` first. Adoptions, the already-covered list and its
  in-tree Sphinx docs are in `retlab-liberation-watch-notes.md`.
- **juanjux's fork** (`juanjux/dcs-escalation`) — upstream's most prolific outside contributor.
  Skim its PR list, `[FIX]` first, and **verify every claim against our own files before
  acting**. His #40 reverted the FLOT-anchored support orbits, as we did independently on
  2026-08-09; do not re-litigate. Ledger: `retlab-juanjux-fork-watch-notes.md`.
- **The MIST author's repositories** — read-only. His name and handle appear nowhere in this
  repo (paid-campaign treatment, 2026-08-20). His other repos are GPL-3 or unlicensed and this
  tree is LGPL-3: read them and reimplement from the DCS API, never vendor a file or commit his
  data. The tree ships upstream's MIST, as upstream does. His published unit dump is a second
  ground truth for sensor ranges; the detection-range check was run 2026-08-20 and found no
  defect — do not re-run it. See `retlab-mist-author-repos-notes.md`.

### Upstream PRs — standing rules

The PR-by-PR record is [retlab-upstream-pr-ledger.md](docs/dev/retlab-upstream-pr-ledger.md).
Read it before opening, updating or re-offering an upstream PR, and re-verify its counts with
GitHub first.

- **The upstream PR freeze is in force.** No new PRs until upstream's next beta; updating an
  existing PR is allowed. **Only the DM lifts it** — commit activity has been misread as the
  lift twice. The evidence to bring the DM is whether `test/1.6` has had a build since
  2026-07-25 (the check is in the ledger; use the unfiltered Actions push view).
- **Exceptions are the DM's, one at a time**, and do not carry over. The ledger lists them;
  #966 (the DTC) is open under one. A PR that answers an open issue in the
  [upstream issue ledger](docs/dev/retlab-upstreaming-inventory.md#upstream-issue-ledger) may
  be opened — check the issue's timeline for linked PRs first (#951 was a duplicate).
- **Do not re-carve:** the HDS support (#956 carries it), #873's culling exemption (premise
  wrong), the Splash Damage tuning (#880, a preference).
- **Fork positions a sync must not undo:** `sweden_2020` keeps the KC-135 (#946's tanker half);
  the ATMOS-X station picker reads `starting_coalition`, not `captured` (#927).
- **Coordinate before carving into:** QRA (#782), frontline (#823, #681), SEAD (#772),
  kneeboard (#754), ATC, player region control (#686). Read #674's thread before carving
  target selection.

---

@docs/dev/CLAUDE-ci.md

---

## PINNED — do not modify

**`latest` git tag** — owned by `softprops/action-gh-release@v2` inside `retlab-latest.yml`.
Do NOT delete it or manually push it — breaking it breaks the URL the squadron bookmarks.

**`retlab-latest.yml`** — the sole rolling-release mechanism. Do NOT modify it without
understanding the impact. Test in a branch and verify the `latest` release after merging.
Do NOT add Discord webhook or other org-level secrets — the workflow uses only `GITHUB_TOKEN`.

**Local Python runtime** — before deleting anything under `tmp/`, inspect `.venv/pyvenv.cfg`.
When it reads `home = ...\tmp\uv-python\cpython-3.11.15-windows-x86_64-none`, that
`tmp/uv-python` directory is the base interpreter for `.venv`, **not a disposable cache**;
deleting it breaks `run_retribution.bat` with "No Python at ...". Never recursively delete
`tmp/` without this check.

**`resources/plugins/splashdamage3/Splash_Damage_3.4.2_RetLab.lua`** — RetLab's buddy-tuned
Splash Damage build. Do NOT overwrite it from upstream, and don't reintroduce the config layer:
the values are locked by design (`overall_scaling=0.6`, `rocket_multiplier=0.8`,
`static_damage_boost=1`, `game_messages=true`). The tuning is a preference, not owed upstream
(#880 closed 2026-08-06, DM call). Upstream's `shipRadarDamageEnable` block is left out;
restoring it is its own call. The `oca_aircraft_damage_boost` block is restored, but **ours
computes AGL inline because upstream's copy calls `getAGL`, defined nowhere** — do not resync
that block until upstream fixes it. History: `retlab-splash-damage-notes.md`.

---

## Conventions

- **Anything published to GitHub is written plain (STANDARD, 2026-08-07 user call).** README,
  wiki pages, PR bodies, changelog entries, issue comments and commit messages state what
  changed and why.
  - No voiceover: no dramatic reveals, no "X isn't a Y — it's a Z", no closing flourish.
  - One fact per line. A bullet that needs three sentences is three bullets or a table.
  - Bold marks a term, not emphasis.
  - Lead with the thing the reader came for: the download, the command, the change.
  - No changelog-in-prose in a reference page; history belongs in the design note.
  - Exempt: in-fiction campaign material (briefing packs, role cards), and mirrored upstream
    wiki pages (fork deltas go in **RetLab:** notes).
  - When a feature is cut, grep the README and `docs/wiki/` for it in the same change.
- **Code comments record why, never what (STANDARD, 2026-08-11 user call).** A comment says
  what the code cannot: a constraint from a flown test, a deliberate exclusion, an upstream bug
  being worked around.
  - Cap a block at ~3 lines; longer rationale goes in the design note with a one-line pointer.
  - A plugin or module header may run to ~15 lines: purpose, the `docs/` pointer, then the
    constraints a reader could undo by accident. Reference: `resources/plugins/intercept/intercept-config.lua`.
  - A pointer must resolve; confirm the file exists before committing it.
  - Data files carry values, not essays.
  - **Compress a constraint comment, never delete it.**
  - Measured 2026-08-11: 8.3% comment density against upstream's 4.8%. Re-measure before
    claiming a cleanup worked.
- **UI text house style (STANDARD, 2026-09-22 DM call).** Every user-visible string is US
  English (field names keep their spelling); nautical miles are `NM`; a setting's description
  renders in full, names another setting by its label rather than "above"/"below", and never
  describes a removed feature as live. `tests/settings/test_settings_text.py` guards the
  settings; rules and backlog are in `retlab-ui-consistency-audit-notes.md`.
- **ADHD-friendly agent output (STANDARD, 2026-07-20).** The reader has ADHD. Follow the
  vendored [`i-have-adhd`](https://github.com/ayghri/i-have-adhd) skill
  (`.claude/skills/i-have-adhd/SKILL.md`, MIT, byte-identical to upstream; keep the sibling
  `LICENSE`) as **always-on**: lead with the next action, number multi-step work, restate
  state each turn, lists capped at 5, no preamble or closing pleasantries, end with one
  concrete next action. The skill's own exceptions apply.
- **When the evidence contradicts the instruction, lead with that and stop (STANDARD,
  2026-08-23 user call).** If a file, manual, log or generated artifact contradicts what was
  asked, the reply opens with that finding and names the source, in two sentences, then asks.
  Do not build the thing and bury the contradiction in a note. (The case: the F-14 route was
  trimmed to fit a "7 waypoint" cap that the Heatblur manual shows is a PTID display rank,
  not a capacity.) A preference cannot be contradicted by evidence; taste calls stand. If the
  call is reaffirmed, build it in full and say so.
- **Ask decisions with the AskUserQuestion widget (STANDARD, 2026-07-21; reaffirmed
  2026-10-08).** Whenever you need a decision, use the widget: recommended option first,
  marked "(Recommended)", a one-line trade-off per option, `multiSelect` when choices aren't
  exclusive, at most 4 questions. Typed "1, 2, 3" lists read as low-effort.
  - **When the widget can't reach the reader** (a project thread, where only the message text
    arrives): numbered questions with lettered options in the message, recommendation marked.
  - A free-text question with no fixed options goes in its own block at the end of the
    message: `> ❓ **Need your call:** <the question>`.
  - Never build a custom widget or Artifact to ask a question.
- **Never name a paid campaign anywhere in the repo (STANDARD, 2026-08-07 user call).**
  Third-party DCS campaigns are commercial products. Studying them and extracting facts is
  fine; their **names** stay out of code, comments, commits, PR titles/bodies, docs and wiki.
  - Use stable letters (`campaign A`, `campaign B`, …), consistent across docs; publishers
    likewise. Install paths are generic: `<DCS>\Mods\campaigns\<campaign A>`.
  - Commit messages and PR metadata count; rewrite and force-push an unmerged branch to fix one.
  - Not covered: real squadron names, real operation names, and the fork's own campaign names.
  - Check against `ls "<DCS>\Mods\campaigns\"`, not memory.
- **Supply lines follow the driveable corridor (STANDARD, 2026-07-03).** Every authored
  `supply_routes:` / shipping-lane drawing traces the road, river valley or pass you would
  drive, never a straight line across a ridgeline. Only the first and last waypoints bind the
  route to its CPs, so use 3–5 intermediates. On real-world maps author them from real road
  lat/lon with `python tools/supply_route_geo.py [coin|red_flag_81_2|caucasus_trail_fixes]`;
  on fictional overlays trace on-map roads by eye. Reference implementations: COIN
  (`coin_enduring_resolve.yaml`) and Red Flag 81-2 (`red_flag_81_2.yaml`).
- **Upstream dev-process standards are ours (ADOPTED 2026-07-20 user call).** The upstream
  wiki's Contributing and Core development guides are mirrored with **RetLab:** deltas in
  `docs/wiki/`: the Developer's Guide (small PRs, type annotations, Black via pre-commit), the
  aircraft/terrain module checklists, the QGIS shapefile guide, Modded-Unit-Support,
  Motorpools, Campaign maintenance, and the Release process (the rolling `latest` IS the
  release; pinned tags are `v<X.Y.Z>-retlab`; never `git push --tags`). Upstream carves meet
  the same standards: target `dcs-retribution/dev` via the PR fork, one change per PR,
  upstream's gates run locally on the upstream tree, a `changelog.md` note, fork-only
  couplings stripped. When an upstream page changes, refresh the mirror and re-annotate.
- **AGENTS.md sync** — `AGENTS.md` is a byte-identical mirror of this file (CLAUDE.md is
  authoritative; only line 1, the title, differs), and `tests/test_agent_guide_mirror.py`
  fails when they drift. After editing CLAUDE.md, resync: `cp CLAUDE.md AGENTS.md`, then Edit
  line 1 back to `# AGENTS.md ...` (do NOT use `sed -i`; it flattens CRLF). The imported
  `docs/dev/CLAUDE-ci.md` is shared by both.
