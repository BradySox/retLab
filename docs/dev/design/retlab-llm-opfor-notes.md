# Outside AI for red: read and report first, commander later · §109

**Status:** stage 1 (read and report) built 2026-10-09, not flown (row B201). Stage 2a
(the AI plans red) built 2026-10-09, not flown (row B204). Stages 2b and 3 agreed, not
started.

## The call, and what it reverses

On 2026-08-24 the DM said *"Long term I don't want the LLM planning red, I wanna use the
LLM to teach the model/Retribution to plan better"*, and the doctrine-mining note recorded
that no LLM runs in this fork. **On 2026-10-09 the DM reversed that**, after reading
juanjux's Escalation README, where the LLM commander is the headline feature:

> Defer to his version, read and report is the primary task for ours.

So RetLab builds Juan's shape (an outside AI that can eventually plan red), and its main
job is the one the August call wanted: an AI that reads red's turn and reports defects,
which we then fix in ordinary planner code. Seam 7 is still dropped as a claim about red's
quality ([retlab-red-brain-phase0-notes.md](retlab-red-brain-phase0-notes.md)); this is a
tool, not evidence that the HTN plans badly.

## Stages

| Stage | What | Status |
|---|---|---|
| 1 | Read API under `/retribution-ai/*` (REST), the `/start` and `/howtoplay` briefings, Developer tools > Copy AI connect link | Built 2026-10-09 |
| 2a | Packages (create, evaluate, delete, TOT), front stances, buying and selling aircraft and ground units, the AI's notes saved with the campaign, Developer tools > Outside AI plans red, the Take Off fallback | Built 2026-10-09 |
| 2b | Loadouts, waypoint edits, ground transfers, ship moves, repairs, squadron moves | Agreed, not started |
| 3 | MCP at `/mcp` for the claude.ai app; the toolbar activity icon and the Take Off lock while the AI works | Agreed, not started |

DM's answers on 2026-10-09: port Juan's code; red sees blue as the scripted planner does,
never blue's ATO; the old planner fills in if the AI does not finish. For stage 2: split
2a/2b; the switch is a Developer tools toggle, not a setting; with it on the AI does all
of red's buying (Juan keeps red's auto-buying running); the AI gets notes saved with the
campaign.

## Stage 2a: who plans red

- **Toggle off** (default): nothing changes. Writes answer 403.
- **Toggle on**: the write routes open. `Coalition.initialize_turn` plans and buys for red
  exactly as with the toggle off, so the AI starts each turn from the scripted plan and
  keeps it, changes it or clears it. Red's runway and SAM repairs (§68) ride on
  `plan_procurement` and keep running.
- **Take Off** (`QTopPanel.launch_mission`): when the toggle is on and red has no
  packages, `service.run_fallback_if_needed` runs `red.plan_missions` and logs a line.
- Any mid-turn `Game.initialize_turn(for_red=True)` replaces red's ATO, the AI's included,
  with a fresh scripted plan. The briefing tells the AI to re-read `/packages`.

**Changed 2026-10-10 (DM call).** As first built, the toggle stood red's `plan_missions`
and `plan_procurement` down. On the first live use (Kola, turn 1) a Time & Weather re-roll
after ticking the box cleared red's 7 scripted packages and refunded its orders with
nothing planned in their place; a turn later red still had no packages and 610 unspent.
The DM's calls: the scripted planner runs before Take Off; it buys too; the Take Off
re-plan fires only when red has no packages, so it never overwrites an AI's plan. The AI
cancels an aircraft order with `sell/aircraft`; it has no route to cancel a ground order.

## Source and licence

Ported from `juanjux/dcs-escalation` (`game/agent/`, `game/server/retributionai/`), LGPL-3
like this tree, so code may be copied with credit; each ported file names its source. His
design docs are `ai-docs/00`-`07` in that repo. Read
[retlab-juanjux-fork-watch-notes.md](retlab-juanjux-fork-watch-notes.md) for how he uses it.

What was left out, because RetLab has no such system: pilot morale, leave and crews, High
Command, rebuild countdowns, the derived IADS state (`state_map`), per-package rationale,
air-assault "remain", and his per-campaign token (we use the per-process key). His
`stored_context` is our `Game.opfor_ai_notes`.
Cruise-missile stock is left out because reading it seeds the magazines (a write).

## Shape

- `game/agent/views.py`: pydantic read models, pure functions over a `Game`.
- `game/agent/service.py`: the one layer every transport calls. `opfor_only` refuses any
  side but red there, not in a router, so a second transport cannot forget it.
- `game/agent/mapimage.py`: a Pillow schematic of the same views; no tiles, no network.
- `resources/agent/start.md`, `howtoplay.md`: the AI's briefings. Ours, not Juan's: his
  playbook (122 KB) teaches a commander; ours teaches a reviewer what a finding is.
- `game/server/retributionai/routes.py`: REST shims. Mounted in `game/server/app.py`.
- `game/server/security.py`: `ApiKeyManager.verify` accepts `X-API-Key` or `?token=`.
  Only the AI routes depend on it; the map server's own routes stay open, as before.
- `game/agent/planner.py`, `schemas.py`: the write path over `PackageFulfiller` and the
  purchase adapters. `ProposedFlight.preferred_squadron` (read by
  `AirWing.best_squadrons_for`) is the one engine change: a named squadron, and only it,
  fills the flight; Juan found a type alone let a sister squadron take its place.
- `game/game.py`: `opfor_ai_enabled`, `opfor_ai_notes` (saved; `__setstate__` defaults).
- `game/coalition.py`: the `initialize_turn` branch.
- `qt_ui/windows/QLiberationWindow.py`: Developer tools > Copy AI connect link and
  Outside AI plans red. `qt_ui/widgets/QTopPanel.py`: the Take Off fallback.
- Tests: `tests/agent/test_read_api.py`, `tests/agent/test_write_api.py`.

## Constraints

- Red only. Blue's ATO is the human's private side of the board; Juan closed the same hole
  in his commit `a9d5c5be`. Everything else about blue is served as ground truth, because
  that is what red's scripted planner reads.
- Reads never mutate. Anything that seeds or caches game state stays out of a read.
- Writes need the toggle on, checked in `service._writable_game`.
- The AI plans through the engine's own planners and purchase adapters, never by building
  flights or waypoints itself, so its plan is one the scripted planner could have made.
- The server binds `::1`. The link is for an AI on the same PC; a web AI needs a tunnel,
  which is stage 3's problem.
- The token is per process: the link dies when Retribution closes.
- Keep `howtoplay.md` true to the engine. When a report turns out to misread a rule, add
  the rule to the briefing's last section.
