import logging
import random
from typing import Any, Union, Tuple, Optional, List

from dcs import Mission
from dcs.country import Country
from dcs.mapping import Vector2, Point
from dcs.mission import StartType as DcsStartType
from dcs.planes import (
    F_14A,
    F_14A_135_GR,
    F_14A_135_GR_Early,
    F_14A_95_GR,
    F_14B,
    F_14BU,
    F_5E_3,
    F_86F_Sabre,
    C_101CC,
    Su_33,
    MiG_15bis,
    M_2000C,
)
from dcs.point import PointAction
from dcs.ships import KUZNECOW
from dcs.terrain import NoParkingSlotError, ParkingSlot
from dcs.unitgroup import (
    FlyingGroup,
    ShipGroup,
    StaticGroup,
    HelicopterGroup,
    PlaneGroup,
)

from game.ato import Flight
from game.ato.flightstate import InFlight
from game.ato.starttype import StartType
from game.ato.traveltime import GroundSpeed
from game.missiongenerator.missiondata import MissionData
from game.naming import namegen
from game.theater import Airfield, ControlPoint, Fob, NavalControlPoint, OffMapSpawn
from game.utils import Distance, feet, meters, nautical_miles
from pydcs_extensions import A_4E_C, VSN_F4B, VSN_F4C

WARM_START_HELI_ALT = meters(500)
WARM_START_ALTITUDE = meters(3000)

# In-flight spawns are MSL for the first waypoint (this can maybe be changed to AGL, but
# AGL waypoints have different piloting behavior, so we need to check whether that's
# safe to do first), so spawn them high enough that they're unlikely to be near (or
# under) the ground, or any nearby obstacles. The highest airfield in DCS is Kerman in
# PG at 5700ft. This could still be too low if there are tall obstacles near the
# airfield, but the lowest we can push this the better to avoid spawning helicopters
# well above the altitude for WP1.
MINIMUM_MID_MISSION_SPAWN_ALTITUDE_MSL = feet(6000)
MINIMUM_MID_MISSION_SPAWN_ALTITUDE_AGL = feet(500)

STACK_SEPARATION = feet(200)

# An on-station spawn sits this far short of the track, on the track's own line,
# so its first leg is flown toward the far end instead of starting on a waypoint.
ON_STATION_LEAD_IN = nautical_miles(3)

RTB_ALTITUDE = meters(800)
RTB_DISTANCE = 5000
HELI_ALT = 500
QRA_AIRSTART_SPEED_MS = 150.0


class FlightGroupSpawner:
    def __init__(
        self,
        flight: Flight,
        country: Country,
        mission: Mission,
        helipads: dict[ControlPoint, list[StaticGroup]],
        ground_spawns_roadbase: dict[ControlPoint, list[Tuple[StaticGroup, Point]]],
        ground_spawns_large: dict[ControlPoint, list[Tuple[StaticGroup, Point]]],
        ground_spawns: dict[ControlPoint, list[Tuple[StaticGroup, Point]]],
        mission_data: MissionData,
    ) -> None:
        self.flight = flight
        self.country = country
        self.mission = mission
        self.helipads = helipads
        self.ground_spawns_roadbase = ground_spawns_roadbase
        self.ground_spawns_large = ground_spawns_large
        self.ground_spawns = ground_spawns
        self.mission_data = mission_data

    def create_flight_group(self) -> FlyingGroup[Any]:
        """Creates the group for the flight and adds it to the mission.

        Each flight is spawned according to its FlightState at the time of mission
        generation. Aircraft that are WaitingForStart will be set up based on their
        StartType with a delay. Note that delays are actually created during waypoint
        generation.

        Aircraft that are *not* WaitingForStart will be spawned in their current state.
        We cannot spawn aircraft mid-taxi, so when the simulated state is near the end
        of a long taxi period the aircraft will be spawned in their parking spot. This
        could lead to problems but that's what loiter points are for. The other pre-
        flight states have the same problem but are much shorter and more easily covered
        by the loiter time. Player flights that are spawned near the end of their cold
        start have the biggest problem but players are able to cut corners to make up
        for lost time.

        Aircraft that are already in the air will be spawned at their estimated
        location, speed, and altitude based on their flight plan.
        """
        self._register_custom_callsign()
        try:
            if (
                self.flight.state.is_waiting_for_start
                or self.flight.state.spawn_type is not StartType.IN_FLIGHT
            ):
                grp = self.generate_flight_at_departure()
            else:
                grp = self.generate_mid_mission()
        finally:
            # Pull the role callsign back out of the shared country pool now that
            # pydcs has stamped it onto THIS group. Left in, next_callsign_category()
            # would randomly hand the role callsign to unrelated auto-named flights
            # of the same country/category (the reported "applied to all aircraft"
            # bug).
            self._deregister_custom_callsign()
        self.flight.group_id = grp.id
        return grp

    def _register_custom_callsign(self) -> None:
        """Register a non-stock callsign into the spawn country's pool before pydcs
        assigns it -- pydcs ValueErrors on a callsign not in that pool (dcs
        ``mission._assign_callsign``). Covers both RetLab role callsigns
        (``Toxic``) and a squadron's custom event callsign (e.g. "Voodoo"); a
        stock pool callsign is already present, so this no-ops for it.
        Records that WE injected the name so :meth:`_deregister_custom_callsign`
        only ever pulls back a name we added, never a stock one. Idempotent; a
        no-op for a category with no callsign pool."""
        callsign = self.flight.callsign
        if callsign is None or callsign.name is None:
            return
        name = callsign.name
        category = self.flight.unit_type.dcs_unit_type.category
        category = "Air" if category == "Interceptor" else category
        pool = self.country.callsign.get(category)
        if pool is not None and name not in pool:
            pool.append(name)
            self._injected_custom_callsign = True

    def _deregister_custom_callsign(self) -> None:
        """Undo :meth:`_register_custom_callsign`: pull the injected callsign back
        out of the country's shared pool once pydcs has stamped it onto this group.
        The group's own callsign is already written into each unit's
        ``callsign_dict`` by ``_assign_callsign``, so removing the name afterward
        leaves this flight untouched -- it only stops pydcs's
        ``next_callsign_category`` (a ``random.choice`` over the pool) from handing
        the name to other auto-named flights of the same country/category (the
        reported "callsign applied to all aircraft" bug). Only removes a name we
        injected, so a stock callsign is never touched."""
        if not getattr(self, "_injected_custom_callsign", False):
            return
        callsign = self.flight.callsign
        if callsign is None or callsign.name is None:
            return
        name = callsign.name
        category = self.flight.unit_type.dcs_unit_type.category
        category = "Air" if category == "Interceptor" else category
        pool = self.country.callsign.get(category)
        if pool is not None and name in pool:
            pool.remove(name)
        self._injected_custom_callsign = False

    def create_idle_aircraft(self) -> Optional[FlyingGroup[Any]]:
        # Register a custom/role callsign into the country pool before pydcs assigns
        # it, exactly as the main spawn path does -- otherwise a squadron with a
        # non-stock callsign (e.g. "Voodoo") ValueErrors in pydcs _assign_callsign
        # when its untasked aircraft are parked here.
        self._register_custom_callsign()
        try:
            group = None
            cp = self.flight.squadron.location
            if self.flight.is_helo or self.flight.is_lha and isinstance(cp, Fob):
                group = self._generate_at_cp_helipad(
                    name=namegen.next_aircraft_name(self.country, self.flight),
                    cp=self.flight.squadron.location,
                )
            elif isinstance(cp, Fob):
                group = self._generate_at_cp_ground_spawn(
                    name=namegen.next_aircraft_name(self.country, self.flight),
                    cp=self.flight.squadron.location,
                )
            elif isinstance(cp, Airfield):
                group = self._generate_at_airfield(
                    name=namegen.next_aircraft_name(self.country, self.flight),
                    airfield=cp,
                )
        finally:
            self._deregister_custom_callsign()
        if group:
            group.uncontrolled = True
        return group

    def create_intercept_template(self, group_name: str) -> Optional[FlyingGroup[Any]]:
        cp = self.flight.squadron.location
        if not isinstance(cp, Airfield):
            return None
        # A QRA squadron may carry a custom/role callsign; register it around the
        # spawn so pydcs can resolve it (see create_idle_aircraft).
        self._register_custom_callsign()
        try:
            group = self._generate_at_airfield(
                name=group_name,
                airfield=cp,
            )
        finally:
            self._deregister_custom_callsign()
        for point in group.points:
            point.speed = QRA_AIRSTART_SPEED_MS
        group.late_activation = True
        return group

    @property
    def start_type(self) -> StartType:
        return self.flight.state.spawn_type

    def generate_flight_at_departure(self) -> FlyingGroup[Any]:
        name = namegen.next_aircraft_name(self.country, self.flight)
        cp = self.flight.departure
        try:
            if self.start_type is StartType.IN_FLIGHT:
                group = self._generate_over_departure(name, cp)
                return group
            elif isinstance(cp, NavalControlPoint):
                group_name = cp.get_carrier_group_name()
                carrier_group = self.mission.find_group(group_name)
                if not isinstance(carrier_group, ShipGroup):
                    raise RuntimeError(
                        f"Carrier group {carrier_group} is a "
                        f"{carrier_group.__class__.__name__}, expected a ShipGroup"
                    )
                return self._generate_at_group(name, carrier_group)
            elif isinstance(cp, Fob):
                is_heli = self.flight.squadron.aircraft.helicopter
                is_vtol = not is_heli and self.flight.squadron.aircraft.lha_capable
                if not is_heli and not is_vtol and not cp.has_ground_spawns:
                    raise RuntimeError(
                        f"Cannot spawn fixed-wing aircraft at {cp} because of insufficient ground spawn slots."
                    )
                is_large = self.flight.unit_type.dcs_unit_type.width > 40

                pilot_count = len(self.flight.roster.members)
                if (
                    not is_heli
                    and self.flight.roster.player_count != pilot_count
                    and not self.flight.coalition.game.settings.ground_start_ai_planes
                ):
                    raise RuntimeError(
                        f"Fixed-wing aircraft at {cp} must be piloted by humans exclusively because"
                        f' the "AI fixed-wing aircraft can use roadbases / bases with only ground'
                        f' spawns" setting is currently disabled.'
                    )
                if cp.has_helipads and (is_heli or is_vtol):
                    pad_group = self._generate_at_cp_helipad(name, cp)
                    if pad_group is not None:
                        return pad_group
                if cp.has_ground_spawns and self.flight.client_count > 0 and is_large:
                    pad_group = self._generate_at_cp_ground_spawn(name, cp, is_large)
                    if pad_group is not None:
                        return pad_group
                if cp.has_ground_spawns and (self.flight.client_count > 0 or is_heli):
                    pad_group = self._generate_at_cp_ground_spawn(name, cp)
                    if pad_group is not None:
                        return pad_group
                    else:
                        pad_group = self._generate_at_cp_ground_spawn(name, cp, True)
                        if pad_group is not None:
                            return pad_group
                return self._generate_over_departure(name, cp)
            elif isinstance(cp, Airfield):
                is_heli = self.flight.squadron.aircraft.helicopter
                if cp.has_helipads and is_heli:
                    pad_group = self._generate_at_cp_helipad(name, cp)
                    if pad_group is not None:
                        return pad_group
                # Large planes (wingspan more than 40 meters, looking at you, C-130)
                # First try spawning on large ground spawns
                # Then try the regular airfield ramp spawns
                is_large = self.flight.unit_type.dcs_unit_type.width > 40
                if (
                    cp.has_ground_spawns
                    and is_large
                    and len(self.ground_spawns_large[cp]) >= self.flight.count
                    and (self.flight.client_count > 0)
                ):
                    pad_group = self._generate_at_cp_ground_spawn(name, cp, is_large)
                    if pad_group is not None:
                        return pad_group
                # Below 40 meter wingspan aircraft
                # First try spawning on regular or roadbase ground spawns
                # Then try the regular airfield ramp spawns
                # Then, if both of the above fail, use the large ground spawns
                if (
                    cp.has_ground_spawns
                    and len(self.ground_spawns[cp])
                    + len(self.ground_spawns_roadbase[cp])
                    + len(self.ground_spawns_large[cp])
                    >= self.flight.count
                    and (self.flight.client_count > 0 or is_heli)
                ):
                    pad_group = self._generate_at_cp_ground_spawn(name, cp)
                    if pad_group is not None:
                        return pad_group

                if (
                    cp.has_ground_spawns
                    and len(self.ground_spawns[cp])
                    + len(self.ground_spawns_roadbase[cp])
                    >= self.flight.count
                    and (self.flight.client_count > 0 or is_heli)
                ):
                    pad_group = self._generate_at_cp_ground_spawn(name, cp)
                    if pad_group is not None:
                        return pad_group
                try:
                    return self._generate_at_airfield(name, cp)
                except NoParkingSlotError:
                    if (
                        cp.has_ground_spawns
                        and len(self.ground_spawns_large[cp]) >= self.flight.count
                        and (self.flight.client_count > 0 or is_heli)
                    ):
                        pad_group = self._generate_at_cp_ground_spawn(name, cp, True)
                        if pad_group is not None:
                            return pad_group
                        else:
                            raise NoParkingSlotError
                return self._generate_at_airfield(name, cp)
            else:
                raise NotImplementedError(
                    f"Aircraft spawn behavior not implemented for {cp} ({cp.__class__})"
                )
        except NoParkingSlotError:
            # A cold/warm start needs a parking slot; large fixed-wing aircraft
            # (e.g. the C-130 SOF insert / transports) often find none on a full
            # field and would otherwise be forced into an air start despite the
            # planned ground start. Fall back to a runway start -- which needs no
            # parking slot -- before the air start, so fixed-wing flights still
            # launch from the field. Helos use helipads/ground spawns and are not
            # affected. (Previously this retry was limited to JAMMING flights.)
            if (
                isinstance(cp, Airfield)
                and not self.flight.is_helo
                and self.start_type in {StartType.COLD, StartType.WARM}
            ):
                try:
                    logging.warning(
                        "No parking slots available for %s. Trying runway start "
                        "before falling back to air start.",
                        self.flight.flight_type.value,
                    )
                    self.flight.start_type = StartType.RUNWAY
                    return self._generate_at_airfield(name, cp)
                except NoParkingSlotError:
                    pass

            # Generated when there is no place on Runway or on Parking Slots
            logging.warning(
                "No room on runway or parking slots. Starting from the air."
            )
            self.flight.start_type = StartType.IN_FLIGHT
            group = self._generate_over_departure(name, cp)
            return group

    def generate_mid_mission(self) -> FlyingGroup[Any]:
        assert isinstance(self.flight.state, InFlight)
        name = namegen.next_aircraft_name(self.country, self.flight)
        speed = self.flight.state.estimate_speed()
        pos = self.flight.state.estimate_position()
        pos += Vector2(random.randint(100, 1000), random.randint(100, 1000))
        alt, alt_type = self.flight.state.estimate_altitude()
        on_station = self._on_station_spawn()
        if on_station is not None:
            pos, alt, alt_type = on_station
        cp = self.flight.squadron.location.id

        if cp not in self.mission_data.cp_stack:
            self.mission_data.cp_stack[cp] = MINIMUM_MID_MISSION_SPAWN_ALTITUDE_AGL

        # We don't know where the ground is, so just make sure that any aircraft
        # spawning at an MSL altitude is spawned at some minimum altitude.
        # https://github.com/dcs-liberation/dcs_liberation/issues/1941
        if alt_type == "BARO" and alt < MINIMUM_MID_MISSION_SPAWN_ALTITUDE_MSL:
            alt = MINIMUM_MID_MISSION_SPAWN_ALTITUDE_MSL

        # Set a minimum AGL value for 'alt' if needed,
        # otherwise planes might crash in trees and stuff.
        if alt_type == "RADIO" and alt < self.mission_data.cp_stack[cp]:
            alt = self.mission_data.cp_stack[cp]
            self.mission_data.cp_stack[cp] += STACK_SEPARATION

        group = self.mission.flight_group(
            country=self.country,
            name=name,
            aircraft_type=self.flight.unit_type.dcs_unit_type,
            airport=None,
            position=pos,
            altitude=alt.meters,
            speed=speed.kph,
            maintask=None,
            group_size=self.flight.count,
            callsign_name=self.flight.callsign.name if self.flight.callsign else None,
            callsign_nr=self.flight.callsign.nr if self.flight.callsign else None,
        )

        group.points[0].alt_type = alt_type
        # pydcs leaves every spawned unit's alt_type at its "BARO" default and
        # DCS places an in-air spawn from the unit record, so a "RADIO" (AGL)
        # air start was actually written as a raw MSL altitude -- tens of meters
        # AGL (or below ground) over high terrain (Red Tide M1: the escort
        # Mi-24s were written alt=500/BARO over a ~600 m Harz FARP). Mirror the
        # point's altitude reference onto the units so an AGL air start is
        # really AGL.
        for unit in group.units:
            unit.alt_type = alt_type
        return group

    def _on_station_spawn(self) -> Optional[Tuple[Point, Distance, str]]:
        """Where a support flight that starts on station spawns, or None.

        Position, altitude and altitude reference. None once the sim has the
        flight on its track, where its estimated position is the better answer.
        See ``support_spawns_on_station`` in game/ato/flightplans/patrolling.py.
        """
        plan = self.flight.flight_plan
        if not getattr(plan, "starts_on_station", False):
            return None
        start, end = plan.layout.patrol_start, plan.layout.patrol_end
        # Only an airborne state can answer; a flight waiting to start has not.
        passed = getattr(self.flight.state, "has_passed_waypoint", None)
        if passed is not None and passed(start):
            return None
        away_from_track = end.position.heading_between_point(start.position)
        pos = start.position.point_from_heading(
            away_from_track, ON_STATION_LEAD_IN.meters
        )
        return pos, start.alt, start.alt_type

    def _generate_at_airfield(
        self,
        name: str,
        airfield: Airfield,
        parking_slots: Optional[List[ParkingSlot]] = None,
    ) -> FlyingGroup[Any]:
        # TODO: Delayed runway starts should be converted to air starts for multiplayer.
        # Runway starts do not work with late activated aircraft in multiplayer. Instead
        # of spawning on the runway the aircraft will spawn on the taxiway, potentially
        # somewhere that they don't fit anyway. We should either upgrade these to air
        # starts or (less likely) downgrade to warm starts to avoid the issue when the
        # player is generating the mission for multiplayer (which would need a new
        # option).
        self.flight.unit_type.dcs_unit_type.load_payloads()
        return self.mission.flight_group_from_airport(
            country=self.country,
            name=name,
            aircraft_type=self.flight.unit_type.dcs_unit_type,
            airport=airfield.airport,
            maintask=None,
            start_type=self._start_type_at_airfield(airfield),
            group_size=self.flight.count,
            parking_slots=parking_slots,
            callsign_name=self.flight.callsign.name if self.flight.callsign else None,
            callsign_nr=self.flight.callsign.nr if self.flight.callsign else None,
        )

    def _generate_over_departure(
        self, name: str, origin: ControlPoint
    ) -> FlyingGroup[Any]:
        at = origin.position

        alt_type = "RADIO"
        on_station = self._on_station_spawn()
        if on_station is not None:
            pos, alt, alt_type = on_station
        elif isinstance(origin, OffMapSpawn):
            alt = self.flight.flight_plan.waypoints[0].alt
            alt_type = self.flight.flight_plan.waypoints[0].alt_type
        elif self.flight.unit_type.helicopter:
            alt = WARM_START_HELI_ALT
        else:
            if origin.id not in self.mission_data.cp_stack:
                min_alt = MINIMUM_MID_MISSION_SPAWN_ALTITUDE_AGL
                self.mission_data.cp_stack[origin.id] = min_alt
            alt = self.mission_data.cp_stack[origin.id]
            self.mission_data.cp_stack[origin.id] += STACK_SEPARATION

        speed = GroundSpeed.for_flight(self.flight, alt)
        if on_station is None:
            pos = at + Vector2(random.randint(100, 1000), random.randint(100, 1000))

        group = self.mission.flight_group(
            country=self.country,
            name=name,
            aircraft_type=self.flight.unit_type.dcs_unit_type,
            airport=None,
            position=pos,
            altitude=alt.meters,
            speed=speed.kph,
            maintask=None,
            group_size=self.flight.count,
            callsign_name=self.flight.callsign.name if self.flight.callsign else None,
            callsign_nr=self.flight.callsign.nr if self.flight.callsign else None,
        )

        group.points[0].alt_type = alt_type
        # pydcs leaves every spawned unit's alt_type at its "BARO" default and
        # DCS places an in-air spawn from the unit record, so a "RADIO" (AGL)
        # air start was actually written as a raw MSL altitude -- tens of meters
        # AGL (or below ground) over high terrain (Red Tide M1: the escort
        # Mi-24s were written alt=500/BARO over a ~600 m Harz FARP). Mirror the
        # point's altitude reference onto the units so an AGL air start is
        # really AGL.
        for unit in group.units:
            unit.alt_type = alt_type
        return group

    def _generate_at_group(
        self, name: str, at: Union[ShipGroup, StaticGroup]
    ) -> FlyingGroup[Any]:
        return self.mission.flight_group_from_unit(
            country=self.country,
            name=name,
            aircraft_type=self.flight.unit_type.dcs_unit_type,
            pad_group=at,
            maintask=None,
            start_type=self._start_type_at_group(at),
            group_size=self.flight.count,
            callsign_name=self.flight.callsign.name if self.flight.callsign else None,
            callsign_nr=self.flight.callsign.nr if self.flight.callsign else None,
        )

    def _generate_at_cp_helipad(
        self, name: str, cp: ControlPoint
    ) -> Optional[FlyingGroup[Any]]:
        try:
            helipad = self.helipads[cp].pop()
        except IndexError as ex:
            logging.warning("Not enough helipads available at " + str(ex))
            if isinstance(cp, Airfield):
                return self._generate_at_airfield(name, cp)
            else:
                return None
            # raise RuntimeError(f"Not enough helipads available at {cp}") from ex

        group = self._generate_at_group(name, helipad)

        # Note : A bit dirty, need better support in pydcs
        group.points[0].action = PointAction.FromGroundArea
        group.points[0].type = "TakeOffGround"
        group.units[0].heading = helipad.units[0].heading
        if self.start_type is not StartType.COLD:
            group.points[0].action = PointAction.FromGroundAreaHot
            group.points[0].type = "TakeOffGroundHot"

        wpt = group.waypoint("LANDING")
        if wpt:
            hpad = self.helipads[self.flight.arrival].pop(0)
            wpt.helipad_id = hpad.units[0].id
            wpt.link_unit = hpad.units[0].id
            self.helipads[self.flight.arrival].append(hpad)

        for i in range(self.flight.count - 1):
            try:
                helipad = self.helipads[cp].pop()
                terrain = cp.coalition.game.theater.terrain
                group.units[1 + i].position = Point(
                    helipad.x, helipad.y, terrain=terrain
                )
                group.units[1 + i].heading = helipad.units[0].heading
            except IndexError as ex:
                logging.warning("Not enough helipads available at " + str(ex))
                if isinstance(cp, Airfield):
                    return self._generate_at_airfield(name, cp)
                else:
                    if isinstance(group, HelicopterGroup):
                        self.country.helicopter_group.remove(group)
                    elif isinstance(group, PlaneGroup):
                        self.country.plane_group.remove(group)
                    return None
        return group

    def _generate_at_cp_ground_spawn(
        self, name: str, cp: ControlPoint, is_large: bool = False
    ) -> Optional[FlyingGroup[Any]]:
        is_airbase = False
        is_roadbase = False
        ground_spawn: Optional[Tuple[StaticGroup, Point]] = None

        if not is_large and len(self.ground_spawns_roadbase[cp]) > 0:
            ground_spawn = self.ground_spawns_roadbase[cp].pop()
            is_roadbase = True
        elif not is_large and len(self.ground_spawns[cp]) > 0:
            ground_spawn = self.ground_spawns[cp].pop()
            is_airbase = True
        elif len(self.ground_spawns_large[cp]) > 0:
            ground_spawn = self.ground_spawns_large[cp].pop()
            is_airbase = True

        if ground_spawn is None:
            logging.warning("Not enough ground spawn slots available at " + cp.name)
            return None

        group = self._generate_at_group(name, ground_spawn[0])

        # Note : A bit dirty, need better support in pydcs
        group.points[0].action = PointAction.FromGroundArea
        group.points[0].type = "TakeOffGround"
        group.units[0].heading = ground_spawn[0].units[0].heading

        self._remove_invisible_farps_if_requested(cp, ground_spawn[0], group)

        # Hot start aircraft which require ground power to start, when ground power
        # trucks have been disabled for performance reasons
        ground_power_available = (
            is_airbase or is_roadbase
        ) and self.flight.coalition.game.settings.ground_start_ground_power_trucks

        # Also hot start aircraft which require ground crew support (ground air or chock removal)
        # which might not be available at roadbases
        if (
            self.start_type is not StartType.COLD
            or (
                not ground_power_available
                and self.flight.unit_type.dcs_unit_type
                in [
                    A_4E_C,
                    F_86F_Sabre,
                    MiG_15bis,
                    F_14A_135_GR,
                    F_14A_135_GR_Early,
                    F_14A_95_GR,
                    F_14B,
                    F_14BU,
                    C_101CC,
                ]
            )
            or (
                self.flight.unit_type.dcs_unit_type
                in [
                    F_5E_3,
                    M_2000C,
                    VSN_F4B,
                    VSN_F4C,
                ]
            )
        ):
            group.points[0].action = PointAction.FromGroundAreaHot
            group.points[0].type = "TakeOffGroundHot"

        try:
            cp.coalition.game.scenery_clear_zones
        except AttributeError:
            cp.coalition.game.scenery_clear_zones = []
        cp.coalition.game.scenery_clear_zones.append(ground_spawn[1])

        for i in range(self.flight.count - 1):
            try:
                terrain = cp.coalition.game.theater.terrain
                if not is_large and len(self.ground_spawns_roadbase[cp]) > 0:
                    ground_spawn = self.ground_spawns_roadbase[cp].pop()
                elif not is_large and len(self.ground_spawns[cp]) > 0:
                    ground_spawn = self.ground_spawns[cp].pop()
                elif len(self.ground_spawns_large[cp]) > 0:
                    ground_spawn = self.ground_spawns_large[cp].pop()
                group.units[1 + i].position = Point(
                    ground_spawn[0].x, ground_spawn[0].y, terrain=terrain
                )
                group.units[1 + i].heading = ground_spawn[0].units[0].heading

                self._remove_invisible_farps_if_requested(cp, ground_spawn[0])
            except IndexError as ex:
                raise NoParkingSlotError(
                    f"Not enough STOL slots available at {cp}"
                ) from ex
        return group

    def _remove_invisible_farps_if_requested(
        self,
        cp: ControlPoint,
        ground_spawn: StaticGroup,
        group: Optional[FlyingGroup[Any]] = None,
    ) -> None:
        if (
            cp.coalition.game.settings.ground_start_airbase_statics_farps_remove
            and isinstance(cp, Airfield)
        ):
            # Remove invisible FARPs from airfields because they are unnecessary
            neutral_country = self.mission.country(
                cp.coalition.game.neutral_country.name
            )
            neutral_country.remove_static_group(ground_spawn)
            if group:
                group.points[0].link_unit = None
                group.points[0].helipad_id = None

    def dcs_start_type(self) -> DcsStartType:
        if self.start_type is StartType.RUNWAY:
            return DcsStartType.Runway
        elif self.start_type is StartType.COLD:
            return DcsStartType.Cold
        elif self.start_type is StartType.WARM:
            return DcsStartType.Warm
        raise ValueError(f"There is no pydcs StartType matching {self.start_type}")

    def _start_type_at_airfield(
        self,
        airfield: Airfield,
    ) -> DcsStartType:
        return self.dcs_start_type()

    def _start_type_at_group(
        self,
        at: Union[ShipGroup, StaticGroup],
    ) -> DcsStartType:
        group_units = at.units
        # Setting Su-33s starting from the non-supercarrier Kuznetsov to take off from
        # runway to work around a DCS AI issue preventing Su-33s from taking off when
        # set to "Takeoff from ramp" (#1352)
        # Also setting the F-14A AI variant to start from cats since they are reported
        # to have severe pathfinding problems when doing ramp starts (#1927)
        if self.flight.unit_type.dcs_unit_type == F_14A or (
            self.flight.unit_type.dcs_unit_type == Su_33
            and group_units[0] is not None
            and group_units[0].type == KUZNECOW.id
        ):
            return DcsStartType.Runway
        else:
            return self.dcs_start_type()
