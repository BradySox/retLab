import itertools
import logging
import math
import random
from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Any, Optional

from dcs import Mission, Point
from dcs.action import AITaskPush, ActivateGroup
from dcs.condition import CoalitionHasAirdrome, TimeAfter
from dcs.planes import AJS37
from dcs.point import MovingPoint, PointProperties
from dcs.task import StartCommand
from dcs.triggers import Event, TriggerOnce, TriggerRule
from dcs.unitgroup import FlyingGroup

from game.ato import Flight, FlightWaypoint, FlightType
from game.ato.flightstate import InFlight, WaitingForStart
from game.ato.flightwaypointtype import FlightWaypointType
from game.ato.starttype import StartType
from game.retlab.range_fuel import flight_external_fuel_lbs
from game.missiongenerator.aircraft.waypoints.cargostop import CargoStopBuilder
from game.missiongenerator.missiondata import MissionData
from game.missiongenerator.refuelrendezvous import refuel_rendezvous
from game.settings import Settings
from game.utils import KG_TO_LBS, feet, nautical_miles, pairwise
from .airassaultingress import AirAssaultIngressBuilder
from .antishipingress import AntiShipIngressBuilder
from .armedreconingress import ArmedReconIngressBuilder
from .baiingress import BaiIngressBuilder
from .casingress import CasIngressBuilder
from .csarpickup import CsarPickupBuilder
from .deadingress import DeadIngressBuilder
from .default import DefaultWaypointBuilder
from .holdpoint import HoldPointBuilder
from .joinpoint import JoinPointBuilder
from .landingpoint import LandingPointBuilder
from .landingzone import LandingZoneBuilder
from .ocaaircraftingress import OcaAircraftIngressBuilder
from .ocarunwayingress import OcaRunwayIngressBuilder
from .reconingress import ReconIngressBuilder
from .pydcswaypointbuilder import PydcsWaypointBuilder, TARGET_WAYPOINTS
from .racetrack import RaceTrackBuilder
from .racetrackend import RaceTrackEndBuilder
from .refuel import RefuelPointBuilder
from .seadingress import SeadIngressBuilder
from .seadsweepingress import SeadSweepIngressBuilder
from .splitpoint import SplitPointBuilder
from .strikeingress import StrikeIngressBuilder
from .sweepingress import SweepIngressBuilder
from .target import TargetBuilder

# Max spacing between commanded-altitude anchors on an AI helicopter route leg. A
# RADIO (AGL) waypoint only anchors the commanded altitude to the terrain at the
# waypoint itself; DCS interpolates straight between waypoints, so a long low leg
# across rising terrain is commanded into the ridge line (the Red Tide M1
# Harz/Sauerland Mi-8/Mi-24 CFITs flew 40-110 km transit legs with no anchor in
# between).
MAX_HELO_ANCHOR_SPACING = nautical_miles(5)


class WaypointGenerator:
    def __init__(
        self,
        flight: Flight,
        group: FlyingGroup[Any],
        mission: Mission,
        time: datetime,
        settings: Settings,
        mission_data: MissionData,
        multiplayer: bool,
    ) -> None:
        self.flight = flight
        self.group = group
        self.mission = mission
        self.time = time
        self.settings = settings
        self.mission_data = mission_data
        # AircraftGenerator.use_client: the mission carries two or more player
        # slots. A single-player mission spawns its lone player flight at the
        # planned start time regardless of never_delay_player_flights.
        self.multiplayer = multiplayer
        #: REFUEL waypoints create_waypoints left out of the mission. The caller
        #: needs them too: a REFUEL waypoint is a fuel source to the bingo
        #: estimator, so a dropped one must leave that list as well.
        self.dropped_refuels: list[FlightWaypoint] = []

    def create_waypoints(self) -> tuple[timedelta, list[FlightWaypoint]]:
        for waypoint in self.flight.points:
            waypoint.tot = None

        waypoints = self.flight.flight_plan.waypoints
        mission_start_time = self.set_takeoff_time(waypoints[0])
        self.set_ground_start_altitude()
        self.repair_ground_level_altitudes()

        # The plan asks for a refuel waypoint whenever the coalition owns a
        # tanker-capable squadron ANYWHERE in theater, and puts it at a point
        # derived from the route alone, never from a tanker. Resolve it here
        # (generation, not planning, so the planner's timing is untouched):
        # onto a real orbit when one can serve this flight, gone when none can
        # or when the jet gets home without it.
        # A stop before the push was asked for on the flight, so it is kept whether
        # or not the jet gets home without it.
        layout = getattr(self.flight.flight_plan, "layout", None)
        pre_push = getattr(layout, "pre_push_refuel", None)
        unneeded = self.gets_home_without_the_tanker()
        for point in self.flight.points:
            if point.waypoint_type is not FlightWaypointType.REFUEL:
                continue
            is_pre_push = point is pre_push
            rendezvous = self.resolve_refuel_position(point.position, is_pre_push)
            if rendezvous is None or (unneeded and not is_pre_push):
                self.dropped_refuels.append(point)
            else:
                # The layout owns this waypoint and both lists here iterate it,
                # so the cockpit, the kneeboard and the map move together.
                point.position = rendezvous
        if self.dropped_refuels:
            # Also drop it from the kneeboard list, or the card numbers a
            # steerpoint the jet does not have and every later row is off by one.
            waypoints = [w for w in waypoints if not self.refuel_was_dropped(w)]

        flown_before_spawn = self.points_flown_before_spawn()

        filtered_points: list[FlightWaypoint] = []
        for point in self.flight.points:
            if point.only_for_player and not self.flight.client_count:
                continue
            if self.refuel_was_dropped(point):
                continue
            if any(point is skipped for skipped in flown_before_spawn):
                continue
            if isinstance(self.flight.state, InFlight):
                if self.flight.flight_type in [
                    FlightType.ESCORT,
                    FlightType.SEAD_ESCORT,
                ]:
                    is_join = point.waypoint_type == FlightWaypointType.JOIN
                    join_passed = self.flight.state.has_passed_waypoint(point)
                    if (
                        is_join
                        and join_passed
                        and point != self.flight.state.current_waypoint
                    ):
                        self.builder_for_waypoint(point).add_tasks(self.group.points[0])
                if point == self.flight.state.current_waypoint:
                    # We don't need to build this waypoint because pydcs did that for
                    # us, but we do need to configure the tasks for it so that mid-
                    # mission aircraft starting at a waypoint with tasks behave
                    # correctly.
                    self.builder_for_waypoint(point).add_tasks(self.group.points[0])
                if not self.flight.state.has_passed_waypoint(point):
                    filtered_points.append(point)
            else:
                filtered_points.append(point)
        # Only add 1 target waypoint for Viggens.  This only affects player flights, the
        # Viggen can't have more than 9 waypoints which leaves us with two target point
        # under the current flight plans.
        # TODO: Make this smarter. It currently targets a random unit in the group.
        # This could be updated to make it pick the "best" two targets in the group.
        if self.flight.unit_type.dcs_unit_type is AJS37 and self.flight.client_count:
            viggen_target_points = [
                (idx, point)
                for idx, point in enumerate(filtered_points)
                if point.waypoint_type in TARGET_WAYPOINTS
            ]
            if viggen_target_points:
                keep_target = viggen_target_points[
                    random.randint(0, len(viggen_target_points) - 1)
                ]
                filtered_points = [
                    point
                    for idx, point in enumerate(filtered_points)
                    if (
                        point.waypoint_type not in TARGET_WAYPOINTS
                        or idx == keep_target[0]
                    )
                ]

        for idx, point in enumerate(filtered_points):
            self.builder_for_waypoint(point).build()

        # AI helicopters get terrain re-anchoring waypoints on long low legs; a
        # human-crewed flight flies its own terrain clearance and does not want
        # the route clutter. Runs before the locked-speed conflict resolver so
        # inserted points can never trip the DCS locked-speed-between-locked-time
        # rejection.
        if self.flight.is_helo and not self.flight.client_count:
            self._insert_helo_terrain_anchors()

        self.ensure_in_flight_route_has_locked_time()
        self._resolve_locked_speed_time_conflicts()

        # Set here rather than when the FlightData is created so they waypoints
        # have their TOTs and fuel minimums set. Once we're more confident in our fuel
        # estimation ability the minimum fuel amounts will be calculated during flight
        # plan construction, but for now it's only used by the kneeboard so is generated
        # late.
        self._estimate_min_fuel_for(waypoints)
        self._estimate_planned_fuel_for(waypoints)

        # In-air starts spawn at the current waypoint, so DCS omits the
        # already-passed waypoints; slice from the spawn waypoint so the kneeboard
        # numbering matches the cockpit.
        kneeboard_waypoints = waypoints
        if isinstance(self.flight.state, InFlight):
            kneeboard_waypoints = waypoints[self.flight.state.waypoint_index :]
        return mission_start_time, kneeboard_waypoints

    def set_ground_start_altitude(self) -> None:
        """Put the takeoff waypoint at the departure field's real elevation.

        pydcs copies the parked unit's altitude (0) onto the waypoint it builds
        for us, so every ground start read as sea level in the ME, on the
        kneeboard card and in the DTC steerpoint. Only the waypoint moves --
        the unit is deliberately left alone so the spawn itself is unchanged.
        """
        if not self.group.points:
            return
        point = self.group.points[0]
        if not str(point.type).startswith("TakeOff"):
            return
        elevation = self.flight.departure.field_elevation
        if elevation.meters <= 0:
            return
        point.alt = round(elevation.meters)
        point.alt_type = "BARO"

    def repair_ground_level_altitudes(self) -> None:
        """Put the recovery waypoints at their field's real elevation.

        The flight-plan layout is pickled into the save, so a campaign already
        in progress would otherwise keep the sea-level 0 these waypoints were
        planned with. Mutating the layout point (as the refuel rendezvous above
        does) keeps the cockpit, the kneeboard and the map on one number.
        """
        for point in self.flight.points:
            if point.waypoint_type is FlightWaypointType.TAKEOFF:
                point.alt = self.flight.departure.field_elevation
                point.alt_type = "BARO"
            elif point.waypoint_type in (
                FlightWaypointType.LANDING_POINT,
                FlightWaypointType.DIVERT,
            ):
                if point.control_point is None:
                    continue
                point.alt = point.control_point.field_elevation
                point.alt_type = "BARO"

    def ensure_in_flight_route_has_locked_time(self) -> None:
        if not self.flight.state.in_flight:
            return
        if any(point.ETA_locked for point in self.group.points):
            return
        if not self.group.points:
            return
        point = self.group.points[0]
        point.ETA = 0
        point.ETA_locked = True
        point.speed_locked = True

    def _resolve_locked_speed_time_conflicts(self) -> None:
        """Unlock speeds DCS's route validator refuses to load the mission with.

        The rule is ``verifyRouteSeg_`` in DCS's own
        ``MissionEditor/modules/me_route.lua``: for every pair of consecutive
        TOT-locked waypoints ``(from, to)``, at least one waypoint in the range
        ``(from, to]`` must have an UNLOCKED speed -- the bounding TOTs already
        determine that segment's timing, so DCS needs one waypoint whose speed
        it is free to solve for. Otherwise the mission refuses to load with
        "All waypoints (N-M) have locked speed and surrounded by waypoints ...
        with locked time!".

        Note the range is INCLUSIVE of ``to``: two ADJACENT TOT-locked
        waypoints are rejected whenever the second one also carries a locked
        speed. That is not a hypothetical -- ``set_waypoint_tot`` speed-locks a
        waypoint whose ETA clamps to 0, so an in-flight (air-started) flight
        whose next TOT has already elapsed spawns with an ETA-0 spawn point
        immediately followed by an ETA-0 TOT waypoint, both speed-locked. A
        turn-2 Marianas J-15 BARCAP hit exactly this ("(2-2) ... waypoints 1
        and 2").

        Repairs, in the order DCS cares about them:

        1. Every speed-locked waypoint strictly between two TOTs is unlocked
           (a carrier escort's clamped JOIN, the inserted helo terrain anchors).
        2. If that leaves the inclusive span with no unlocked speed at all --
           i.e. the two TOTs are adjacent and the closing one is speed-locked --
           the closing waypoint's speed lock is dropped too.

        Times are never touched: they sync the flight with its package, and the
        first waypoint's TOT is required by late activation. Split/RTB legs keep
        their locked speed since no TOT-locked waypoint follows them.
        """
        points = self.group.points
        n = len(points)
        if n < 2:
            return

        def eta_locked(index: int) -> bool:
            return bool(getattr(points[index], "ETA_locked", False))

        def unlock(index: int, reason: str) -> None:
            points[index].speed_locked = False
            logging.debug(
                "%s: unlocked speed on waypoint %d (%s); %s is rejected by DCS.",
                self.flight,
                index,
                getattr(points[index], "name", ""),
                reason,
            )

        start = 0
        while start < n - 1:
            # The closing waypoint of this segment, mirroring DCS's own walk:
            # the next TOT-locked waypoint, else the end of the route.
            end = next((i for i in range(start + 1, n) if eta_locked(i)), n - 1)
            if eta_locked(start) and eta_locked(end):
                for i in range(start + 1, end):
                    if getattr(points[i], "speed_locked", False):
                        unlock(i, "a locked speed between TOT-locked waypoints")
                span = range(start + 1, end + 1)
                if all(getattr(points[i], "speed_locked", False) for i in span):
                    unlock(
                        end,
                        "a locked speed on every waypoint between two TOT-locked "
                        "waypoints",
                    )
            start = end

    def _insert_helo_terrain_anchors(self) -> None:
        """Subdivide long AGL helo route legs with terrain re-anchoring points.

        A RADIO (AGL) waypoint anchors the commanded altitude to the terrain at
        the waypoint only, and the helo AI does not reliably terrain-follow
        between waypoints. Each inserted point is a speed-locked Turning Point
        at the leg's altitude (floored at the helo cruise AGL setting),
        alt_type RADIO, so the commanded profile re-anchors to local terrain at
        most MAX_HELO_ANCHOR_SPACING apart instead of being interpolated
        straight across a ridge line. Only legs whose both ends are already
        RADIO are touched, and never the racetrack orbit leg (its start->end
        adjacency IS the orbit definition). Tasks, TOTs, CTLD landing zones and
        the kneeboard (built from the flight plan, not these pydcs points) are
        untouched.

        The lock flags matter: DCS rejects a route at mission start when a
        waypoint has BOTH speed and ETA unlocked without being bracketed by
        ETA-locked waypoints ("has both unlocked speed and time and not
        surrounded by waypoints with locked time" -- the first generated Red
        Tide M2 tripped this on every subdivided helo RTB leg), and also
        rejects the inverse (a locked speed BETWEEN ETA-locked waypoints). So
        anchors insert speed-locked -- the legal state everywhere else -- and
        _resolve_locked_speed_time_conflicts, which runs right after, unlocks
        any anchor that landed between TOT-locked waypoints.
        """
        spacing = MAX_HELO_ANCHOR_SPACING.meters
        cruise_agl_m = feet(self.settings.heli_cruise_alt_agl).meters
        points = self.group.points
        i = 0
        while i < len(points) - 1:
            a, b = points[i], points[i + 1]
            if (
                a.alt_type != "RADIO"
                or b.alt_type != "RADIO"
                or a.name == "RACETRACK START"
            ):
                i += 1
                continue
            leg = a.position.distance_to_point(b.position)
            if leg <= spacing:
                i += 1
                continue
            segments = math.ceil(leg / spacing)
            alt = int(round(max(a.alt, b.alt, cruise_agl_m)))
            for n in range(1, segments):
                anchor = MovingPoint(a.position.lerp(b.position, n / segments))
                anchor.name = "TERRAIN"
                anchor.alt = alt
                anchor.alt_type = "RADIO"
                anchor.speed = b.speed
                anchor.ETA_locked = False
                anchor.speed_locked = True
                anchor.properties = PointProperties()
                points.insert(i + n, anchor)
            i += segments

    def points_flown_before_spawn(self) -> list[FlightWaypoint]:
        """The way out to the track, for a support flight that spawns on it.

        Left in the route, DCS flies the group back to them from the track.
        """
        plan = self.flight.flight_plan
        if not getattr(plan, "starts_on_station", False):
            return []
        return list(plan.layout.nav_to)

    def refuel_was_dropped(self, waypoint: FlightWaypoint) -> bool:
        return any(waypoint is dropped for dropped in self.dropped_refuels)

    def resolve_refuel_position(
        self, planned: Point, pre_push: bool = False
    ) -> Optional[Point]:
        """Where the REFUEL waypoint belongs, or None to drop it entirely.

        ``mission_data.tankers`` is the generated truth -- the tankers that exist
        in the .miz, and where they orbit -- rather than the planner's "does this
        coalition own a tanker squadron", which is what puts a refuel waypoint on
        a 14 nm carrier escort. Absent tanker data (lightweight test doubles)
        leaves the planned point alone so nothing moves or drops on a guess.
        """
        tankers = getattr(self.mission_data, "tankers", None)
        if tankers is None:
            return planned
        # `blue` is a Player enum, so it is ALWAYS truthy -- pass `.is_blue`,
        # never the object. A bare truthiness test would match every tanker and
        # quietly turn this into a no-op.
        return refuel_rendezvous(
            self.flight.unit_type,
            self.flight.blue.is_blue,
            planned,
            tankers,
            theater_only=pre_push,
        )

    #: Landing reserves the dry margin must clear before a refuel waypoint is
    #: dropped as unearned. Measured data gets 2x the airframe's own min-safe;
    #: a synthesised model gets 3x, because the number is a guess and the cost
    #: of being wrong is a flight that does not reach its field.
    REFUEL_DROP_RESERVES_MEASURED = 2.0
    REFUEL_DROP_RESERVES_ESTIMATED = 3.0

    def gets_home_without_the_tanker(self) -> bool:
        """True when the planned sortie lands with fuel to spare, never plugging in.

        The refuel waypoint is not a fuel-need test at planning time, so a B-1B
        with 89% of its fuel left flew 66 km PAST its own field to a tanker it
        did not need and was still out there at mission end (test 36). The dry
        margin is the burn with no top-off applied, so a flight that clears the
        bar never needed the gas; and dropping the waypoint only shortens the
        route, so the margin after the drop can only be larger than the one
        tested here.
        """
        from game.retlab.fuel_brief import fuel_brief_for

        if not any(
            point.waypoint_type is FlightWaypointType.REFUEL
            for point in self.flight.points
        ):
            # Nothing to drop; skip the fuel walk for the flights that are the
            # majority of any ATO.
            return False
        brief = fuel_brief_for(self.flight)
        if brief is None or not brief.refuel_passes:
            # No fuel model for the airframe, or nothing to drop. Leave the
            # planner's decision alone rather than guess.
            return False
        reserves = (
            self.REFUEL_DROP_RESERVES_ESTIMATED
            if brief.estimated
            else self.REFUEL_DROP_RESERVES_MEASURED
        )
        return brief.dry_margin_lbs >= brief.reserve_lbs * reserves

    def builder_for_waypoint(self, waypoint: FlightWaypoint) -> PydcsWaypointBuilder:
        builders = {
            FlightWaypointType.CARGO_STOP: CargoStopBuilder,
            FlightWaypointType.CSAR_PICKUP: CsarPickupBuilder,
            FlightWaypointType.DROPOFF_ZONE: LandingZoneBuilder,
            FlightWaypointType.INGRESS_AIR_ASSAULT: AirAssaultIngressBuilder,
            FlightWaypointType.INGRESS_ANTI_SHIP: AntiShipIngressBuilder,
            FlightWaypointType.INGRESS_ARMED_RECON: ArmedReconIngressBuilder,
            FlightWaypointType.INGRESS_BAI: BaiIngressBuilder,
            FlightWaypointType.INGRESS_CAS: CasIngressBuilder,
            FlightWaypointType.INGRESS_DEAD: DeadIngressBuilder,
            FlightWaypointType.INGRESS_OCA_AIRCRAFT: OcaAircraftIngressBuilder,
            FlightWaypointType.INGRESS_OCA_RUNWAY: OcaRunwayIngressBuilder,
            FlightWaypointType.INGRESS_SEAD: SeadIngressBuilder,
            FlightWaypointType.INGRESS_SEAD_SWEEP: SeadSweepIngressBuilder,
            FlightWaypointType.INGRESS_RECON: ReconIngressBuilder,
            FlightWaypointType.INGRESS_STRIKE: StrikeIngressBuilder,
            FlightWaypointType.INGRESS_SWEEP: SweepIngressBuilder,
            FlightWaypointType.JOIN: JoinPointBuilder,
            FlightWaypointType.LANDING_POINT: LandingPointBuilder,
            FlightWaypointType.LOITER: HoldPointBuilder,
            FlightWaypointType.PATROL: RaceTrackEndBuilder,
            FlightWaypointType.PATROL_TRACK: RaceTrackBuilder,
            FlightWaypointType.PICKUP_ZONE: LandingZoneBuilder,
            FlightWaypointType.REFUEL: RefuelPointBuilder,
            FlightWaypointType.SPLIT: SplitPointBuilder,
            FlightWaypointType.TARGET_GROUP_LOC: TargetBuilder,
            FlightWaypointType.TARGET_POINT: TargetBuilder,
        }
        builder = builders.get(waypoint.waypoint_type, DefaultWaypointBuilder)
        return builder(
            waypoint,
            self.group,
            self.flight,
            self.mission,
            self.time,
            self.mission_data,
        )

    def _estimate_min_fuel_for(self, waypoints: list[FlightWaypoint]) -> None:
        # Fall back to a rough estimate from fuel capacity for the many airframes with
        # no hand-measured data, so the kneeboard fuel ladder still renders. This stays
        # out of the planner / sim, which read unit_type.fuel_consumption directly.
        consumption = (
            self.flight.unit_type.fuel_consumption
            or self.flight.unit_type.estimated_fuel_consumption
        )
        if consumption is None:
            return

        min_fuel: float = consumption.min_safe

        # The flight plan (in reverse) up to and including the arrival point.
        main_flight_plan: Iterator[FlightWaypoint] = reversed(waypoints)
        try:
            while waypoint := next(main_flight_plan):
                if waypoint.waypoint_type is FlightWaypointType.LANDING_POINT:
                    waypoint.min_fuel = min_fuel
                    main_flight_plan = itertools.chain([waypoint], main_flight_plan)
                    break
        except StopIteration:
            # Some custom flight plan without a landing point. Skip it.
            return

        for b, a in pairwise(main_flight_plan):
            for_leg = self.flight.flight_plan.fuel_consumption_between_points(
                a, b, consumption
            )
            if for_leg is None:
                continue
            min_fuel += for_leg
            # No reset at a REFUEL waypoint: a planned tanker pass is not gas
            # taken, so the minimum is always the fuel to get home unrefuelled
            # (the rule fuel_brief and the bingo estimate follow).
            a.min_fuel = min_fuel

    def _estimate_planned_fuel_for(self, waypoints: list[FlightWaypoint]) -> None:
        """Forward-estimate the fuel remaining at each waypoint (the "fuel ladder").

        Mirrors ``_estimate_min_fuel_for`` but walks forward from the starting load,
        subtracting each leg's burn, so the kneeboard can show planned remaining
        alongside the minimum required. Tops back up to a full load at a tanker
        (REFUEL) waypoint. Falls back to a capacity-derived estimate for airframes
        with no measured data; a no-op only when even that is unavailable (no fuel
        capacity) or there is no starting fuel.
        """
        consumption = (
            self.flight.unit_type.fuel_consumption
            or self.flight.unit_type.estimated_fuel_consumption
        )
        start_fuel_kg = getattr(self.flight, "fuel", None)
        if consumption is None or start_fuel_kg is None:
            return

        # Count the external tanks (§46 fuel-first planning fits them at plan
        # time), or the ladder contradicts the tanker decision -- a three-bag jet
        # would read "short of home" on a sortie its real load covers.
        full_load_lbs = start_fuel_kg * KG_TO_LBS + flight_external_fuel_lbs(
            self.flight
        )
        remaining = full_load_lbs - consumption.taxi
        previous: FlightWaypoint | None = None
        for waypoint in waypoints:
            if previous is not None:
                for_leg = self.flight.flight_plan.fuel_consumption_between_points(
                    previous, waypoint, consumption
                )
                if for_leg is not None:
                    remaining -= for_leg
            if waypoint.waypoint_type is FlightWaypointType.REFUEL:
                remaining = full_load_lbs
            waypoint.fuel_planned = max(0.0, remaining)
            previous = waypoint

    def set_takeoff_time(self, waypoint: FlightWaypoint) -> timedelta:
        if isinstance(self.flight.state, WaitingForStart):
            delay = self.flight.state.time_remaining(self.time)
        else:
            delay = timedelta()

        placement_delay = self.needs_deck_placement_delay()

        if self.should_delay_flight() or (
            placement_delay and not self.flight.client_count
        ):
            if self.should_activate_late():
                # Late activation causes the aircraft to not be spawned
                # until triggered. A late spawn is also automatically clear of
                # the six-pack, but never activate a carrier group at exactly
                # t=0 or it joins the mission-start deck fill anyway.
                if placement_delay:
                    delay = max(delay, timedelta(seconds=1))
                self.set_activation_time(delay)
            elif self.flight.start_type is StartType.COLD:
                # Setting the start time causes the AI to wait until the
                # specified time to begin their startup sequence. The group
                # spawns at mission start, so player slots exist from the
                # start of the mission (unlike late activation).
                self.set_startup_time(delay)
                if placement_delay:
                    # An uncontrolled group still spawns with the mission-start
                    # deck fill; activating it a second late keeps it clear of
                    # the six-pack while the StartCommand above still holds the
                    # AI to the planned push time.
                    self.set_activation_time(timedelta(seconds=1))
        elif placement_delay:
            # No startup hold owed, but the group must still spawn a second
            # late to stay clear of the six-pack.
            self.set_activation_time(timedelta(seconds=1))

        # And setting *our* waypoint TOT causes the takeoff time to show up in
        # the player's kneeboard.
        waypoint.tot = self.flight.flight_plan.takeoff_time()
        return delay

    def needs_deck_placement_delay(self) -> bool:
        """Whether this group must spawn at least a second after mission start.

        https://github.com/dcs-liberation/dcs_liberation/issues/1309
        The mission-start spawn wave fills the carrier six-pack first, which
        sits in the taxi lane to the bow catapults: AI parked there deadlock
        the deck, and a slow-starting player parked there jams every AI jet
        taxiing to launch. Delaying a carrier deck spawn by one second causes
        DCS to place the aircraft elsewhere on deck, so AI carrier ground
        starts always take the delay, and player flights take it too under the
        never: a late-activated client group in multiplayer shows its slots as
        a "delayed start" nobody can fly (test 54, 2026-10-07).
        """
        if self.flight.state.in_flight:
            return False
        if self.flight.state.spawn_type not in (StartType.COLD, StartType.WARM):
            return False
        if not self.flight.departure.is_fleet:
            return False
        return not self.flight.client_count

    def set_activation_time(self, delay: timedelta) -> None:
        # Note: Late activation causes the waypoint TOTs to look *weird* in the
        # mission editor. Waypoint times will be relative to the group
        # activation time rather than in absolute local time. A flight delayed
        # until 09:10 when the overall mission start time is 09:00, with a join
        # time of 09:30 will show the join time as 00:30, not 09:30.
        self.group.late_activation = True

        activation_trigger = TriggerOnce(
            Event.NoEvent, f"FlightLateActivationTrigger{self.group.id}"
        )
        activation_trigger.add_condition(TimeAfter(seconds=int(delay.total_seconds())))

        self.prevent_spawn_at_hostile_airbase(activation_trigger)
        activation_trigger.add_action(ActivateGroup(self.group.id))
        self.mission.triggerrules.triggers.append(activation_trigger)

    def prevent_spawn_at_hostile_airbase(self, trigger: TriggerRule) -> None:
        # Prevent delayed flights from spawning at airbases if they were
        # captured before they've spawned.
        if (airport := self.flight.departure.dcs_airport) is not None:
            trigger.add_condition(
                CoalitionHasAirdrome(
                    self.flight.squadron.coalition.coalition_id, airport.id
                )
            )

    def set_startup_time(self, delay: timedelta) -> None:
        # Uncontrolled causes the AI unit to spawn, but not begin startup.
        self.group.uncontrolled = True

        activation_trigger = TriggerOnce(
            Event.NoEvent, f"FlightStartTrigger{self.group.id}"
        )
        activation_trigger.add_condition(TimeAfter(seconds=int(delay.total_seconds())))

        self.prevent_spawn_at_hostile_airbase(activation_trigger)
        self.group.add_trigger_action(StartCommand())
        activation_trigger.add_action(AITaskPush(self.group.id, len(self.group.tasks)))
        self.mission.triggerrules.triggers.append(activation_trigger)

    def should_delay_flight(self) -> bool:
        if not isinstance(self.flight.state, WaitingForStart):
            return False

        if not self.flight.client_count:
            return True

        if self.flight.state.time_remaining(self.time) < timedelta(minutes=10):
            # Don't bother delaying client flights with short start delays. Much more
            # than ten minutes starts to eat into fuel a bit more (especially for
            # something fuel limited like a Harrier).
            return False

        if not self.multiplayer:
            # "Spawn player flights immediately" exists to keep MP slots
            # selectable from mission start. With fewer than two player slots
            # there is no slot list to protect, so the lone player flight is
            # delayed to its planned start time instead of idling from t=0.
            return True

        return not self.settings.never_delay_player_flights

    def should_activate_late(self) -> bool:
        if self.flight.start_type is not StartType.COLD:
            # Avoid spawning aircraft in the air or on the runway until it's
            # time for their mission. Also avoid burning through gas spawning
            # hot aircraft hours before their takeoff time.
            return True

        if self.flight.client_count and not self.multiplayer:
            # A delayed single-player cold start materializes at its planned
            # startup time instead of spawning uncontrolled at mission start:
            # there is no MP slot list to keep populated, and an uncontrolled
            # spawn would leave the lone player idling in the pit from t=0.
            return True

        if self.flight.departure.is_fleet and not self.flight.client_count:
            # AI carrier spawns will crowd the carrier deck, especially without
            # super carrier, so only spawn them when needed. Client carrier
            # flights instead spawn uncontrolled like their airfield
            # counterparts (plus a one-second activation for six-pack
            # placement) so their slots exist for players from the start of
            # the mission rather than appearing only at the push time.
            # TODO: Is there enough parking on the supercarrier?
            return True

        return False
