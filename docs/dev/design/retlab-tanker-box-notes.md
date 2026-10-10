# Theater tanker track and tanker orbit speed

**Status:** every theater tanker flies a 40 NM racetrack again (2026-10-09, DM call). The
four-corner **tanker box** that replaced it from 2026-09-28 was removed: flown with a jet
on the boom, the tanker never levelled out (see *The box, and why it was removed*). The
orbit speed is live: per flight, on a tanker flight's Waypoints tab, saved per airframe by
the Payload tab's **Save as default**. Rows B152 (speed) and B206 (racetrack and map
drag); B153 and B170 (the box) are closed.

## Tanker orbit speed (upstream #869)

- **Per flight, never a campaign setting** (DM 2026-09-28: "never a theatre option. Per
  airframe in the waypoint/loadout setting menu"). `Flight.orbit_speed_kias`, None = the
  aircraft's own speed. Set on the tanker flight's Waypoints tab (`QTankerOrbitSpeed`,
  100-350 KIAS; on the Payload tab until 2026-09-29). **Save as default** stores it per airframe in §43's store
  (`orbit_speed_kias`), so every new flight of that type starts with it.
- The KIAS is converted to true airspeed at the track altitude: `Speed.from_calibrated`,
  ISA atmosphere with the compressible pitot relation. DCS waypoint and orbit speeds are TAS.
- Applies to theater and package tankers (`RefuelingFlightPlan.patrol_speed`).
- **Not** the carrier recovery tanker: its speed comes from the `RecoveryTanker` task
  (`honors_orbit_speed = False`).
- No helicopter-tanker floor: the first cut skipped anything under 200 KIAS, but a
  per-airframe choice is the user's, and 120-130 KIAS is how a KC-130J serves helicopters.
- Capped at the airframe's pydcs `max_speed`. The legacy KC-130 tops out at 335 KTAS, which is
  under 270 KIAS at 20,000 ft, so it flies at its top speed.
- **Flown 2026-10-09** (Kola, KC-135 at 20,000 ft, 280 KIAS set): the `.miz` carried
  374.6 KTAS and the tanker's ground speed averaged 376 kt over opposite legs.

## The racetrack

- **Layout.** `TheaterRefuelingFlightPlan` lays out a `PatrollingLayout`: RACETRACK START
  and RACETRACK END, `TANKER_TRACK_LENGTH` (40 NM, upstream's value) apart, across the
  threat axis, `tanker_threat_buffer_min_distance` outside the threat zone. DCS flies it
  with its own Orbit task (Race-Track pattern).
- **Several tankers.** Each further tanker in a package sits `TANKER_ORBIT_SPACING` (15 NM)
  further back from the threat.
- **Altitude between packages.** Every theater tanker on a side takes its own altitude,
  2,000 ft from every other (`deconflicted_altitude`: its planned altitude, then up or down
  in 2,000 ft steps, higher first, inside the doctrine's combat band). Added 2026-10-08
  after Anatolian Reach turn 1 put the carrier's KC-135 and Akrotiri's MPRS tanker on
  overlapping tracks at 24,000 ft.
- **Moving it on the app map** (`move_track`, called from the map's `set_position`
  endpoint; DM 2026-10-09). Dragging RACETRACK START moves the whole track. Dragging
  RACETRACK END swings the track around its start and keeps its length. The marker's
  tooltip says which (`FlightWaypointJs.drag_note`). Theater tankers only: a package
  tanker, AEW&C or CAP track moves one point at a time, as before.
- **Package tankers** fly the same kind of racetrack from their own builder.

### What the racetrack flies (measured)

Tests 36, 38 and 46, KC-135 and KC-135 MPRS, no receiver:

- 39-41 NM straight legs, 5.0-5.8 minutes wings level each (421-470 kt ground speed).
- One 180-degree turn at each end: about 2 minutes at 30 degrees of bank.

No recording has a jet on the boom of a racetrack tanker. At the 15 degrees the box showed
in contact, a 180 would take about 4 minutes at 375 kt. That is an estimate.

## The box, and why it was removed

Built 2026-09-28 on the DM's ask for a tanker box instead of a two-point racetrack; always
on from 2026-09-29; shrunk from 40 x 20 NM to 30 x 15 NM the same day; removed 2026-10-09.

DCS's Orbit task has two patterns, Circle and Race-Track, so the box was a **route**: BOX 1
(the patrol start), three NAV corners, and BOX END back on BOX 1, with the Tanker task
active and a `SwitchWaypoint` looping BOX END to BOX 2 until the on-station time was up.

**Flown 2026-10-09** (Kola, KC-135 at 20,000 ft and about 375 kt, a human F-16 on the boom,
Tacview `Tacview-20261009-190403-DCS-Host-Cost of Living Adjustment`):

- The KC-135's bank in a turn depends on its receivers: **45 degrees alone, 25 degrees with
  a jet joined up, 15 degrees with a jet in contact.**
- At 15 degrees and 375 kt the turn radius is about 8 NM. A 15 NM side is all turn, and a
  30 NM side leaves about 14 NM.
- The route AI does not lead those turns. It overshot each corner and S-turned back.
- The receiver was within 200 ft of the tanker for 6 of 8 minutes close aboard. The tanker
  was wings level for under a minute of the 8. The last 6 minutes 15 seconds were one
  continuous turn: left, right, then left again.
- Alone, on the same box, its longest level stretch was 3.9 minutes.
- At BOX END every lap it overflew the point, turned 117 degrees and corrected back 18-25,
  so the front leg, where receivers were sent, was the most broken one.

**Before trying a box again:** size every side for the 15-degree in-contact turn (two turn
radii plus the level time wanted), and expect the overshoot and S-turn at each corner
anyway, because a route waypoint with a task on it is flown over, not led. The racetrack
gives the same total turning (360 degrees a lap) in two turns DCS flies itself.

### What went with it

- `TankerBoxLayout`, its timing and fuel overrides (the whole on-station time sat on the
  BOX 1 to BOX 2 leg, which is why the kneeboard and the app showed BOX 2-4 at the last
  lap's times), the `SwitchWaypoint` loop, the F10 polygon and the cockpit four-corner
  drawing.
- Kept: the cockpit support box takes its half-width from the tanker's orbit speed (#1097).
- **Old saves.** A save from the box's 11 days pickled `TankerBoxLayout`. The class
  survives as a loader only: `__setstate__` moves the patrol end to the first corner and
  turns the object into a `PatrollingLayout`, so the turn flies the racetrack on the box's
  30 NM front leg. `Flight.__setstate__` still drops the older `tanker_box` flag, and §43
  ignores an old store's `tanker_box` key.

## Refuel before the push (2026-10-07)

A receiver can tank on the theater tanker's track before its package pushes: the Waypoints
tab's **Refuel before the push** (features doc, Refuelling). Only a theater tanker is
used, because a package tanker comes on station after the strike. Row B189.
BARCAP and TARCAP get the same as **Refuel before station** (2026-10-08, row B191).
The second stop (after the strike, or a TARCAP's off station) stays only when the fuel walk
with the first top-off lands under the reserve, and the tab then names the shortfall
(2026-10-09, DM call: keep it and say why, rather than always drop it; row B200).
**Minutes on the tanker** (2026-10-09, DM call, row B202) sets the time planned for the
stop before the push or station only, 1-60 min, starting at 4 a jet plus 1. The stop after
the strike gets no time allowance, as before. AI jets tank until full regardless.

### Verified

- `tests/ato/flightplans/test_theater_tanker_track.py`: the 40 NM racetrack, the spacing,
  the altitude steps, the map drag (move and swing), the tooltip note, a saved box loading
  as a racetrack.
- **Not flown since the return.** Filling up on one leg, and the map drag in the app, are
  row B206.

## On station at mission start, and neutral airspace (2026-10-10)

Read off turn 1 of a Kola game through the outside-AI link:

- The A-50 and IL-78 air-started over Severomorsk-1 and Olenya, 190 and 210 NM from
  their tracks, and were on station 31 and 34 minutes in. The air-start setting says on
  station from mission start. An AI AEW&C or theater tanker under that setting now
  spawns 3 NM short of its track start, on the track's own line, so its first leg is
  flown toward the far end.
- The tanker's track ran 11 NM into neutral Finland and the A-50's ended 4 NM from the
  border. Sliding a track back toward its anchor does not clear it on this map: the line
  from the Kola bases runs through Finland, and back needed 120 and 110 NM. Sliding along
  the track's own length needed 22 and 5 NM and keeps the distance from the threat.
- Not changed: red's strikers and the tanker's flight home still cross about 70 NM of
  Finland. §98 never engages AI, so this is a track placement rule, not a route rule.

Not flown. Row B208.
