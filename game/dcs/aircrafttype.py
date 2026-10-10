from __future__ import annotations

import inspect
import logging
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from functools import cache, cached_property
from pathlib import Path
from typing import Any, ClassVar, Dict, Iterator, Optional, TYPE_CHECKING, Type

import yaml
from dcs.helicopters import helicopter_map
from dcs.planes import plane_map
from dcs.task import AWACS, Reconnaissance, Refueling, Transport
from dcs.unitpropertydescription import UnitPropertyDescription
from dcs.unittype import FlyingType
from dcs.weapons_data import weapon_ids

from game.ato import FlightType
from game.data.units import HEAVY_BOMBER_DCS_IDS, UnitClass
from game.dcs.aircraftproperties import PropertyDateGate
from game.dcs.lasercodeconfig import LaserCodeConfig
from game.dcs.unittype import UnitType
from game.persistency import user_custom_weapon_injections_dir
from game.radio.channels import (
    ApacheChannelNamer,
    ChannelNamer,
    CommonRadioChannelAllocator,
    FarmerRadioChannelAllocator,
    HueyChannelNamer,
    LegacyWarthogChannelNamer,
    MirageChannelNamer,
    MirageF1CEChannelNamer,
    NoOpChannelAllocator,
    RadioChannelAllocator,
    SCR522ChannelNamer,
    SCR522RadioChannelAllocator,
    SingleRadioChannelNamer,
    TomcatChannelNamer,
    ViggenChannelNamer,
    ViggenRadioChannelAllocator,
    ViperChannelNamer,
    WarthogChannelNamer,
    PhantomChannelNamer,
    KiowaChannelNamer,
    ARC5RadioChannelAllocator,
    ARC5ChannelNamer,
    FulcrumChannelNamer,
)
from game.utils import (
    Distance,
    ImperialUnits,
    KG_TO_LBS,
    MetricUnits,
    NauticalUnits,
    SPEED_OF_SOUND_AT_SEA_LEVEL,
    Speed,
    UnitSystem,
    feet,
    knots,
    kph,
    nautical_miles,
)

if TYPE_CHECKING:
    from game.missiongenerator.aircraft.flightdata import FlightData
    from game.missiongenerator.missiondata import MissionData
    from game.radio.radios import Radio, RadioFrequency, RadioRegistry


# Fallback altitude bands (in thousands of feet) used by `preferred_altitude` to
# estimate a flight altitude when an aircraft's data file does not override it. Each
# tuple is (low, high): the altitude a 600 kph aircraft prefers and the altitude a
# 2800 kph aircraft prefers, with faster types interpolated toward the high end. A
# low == high pair pins every aircraft to that single altitude regardless of speed.
# Tune here rather than at the call sites; per-aircraft overrides still win.
PATROL_ALTITUDE_BAND_KFT = (10, 33)
CRUISE_ALTITUDE_BAND_KFT = (20, 20)
COMBAT_ALTITUDE_BAND_KFT = (20, 20)


class AirRefuelType(Enum):
    """Air-to-air refueling method an aircraft uses (as a receiver) or provides (as a
    tanker).

    BOOM is the USAF flying-boom receptacle (KC-135, KC-10); PROBE is probe-and-drogue
    (US Navy/Marine, NATO, most non-US types, and buddy/carrier tankers). The two are
    physically incompatible, so a boom-only receiver cannot take fuel from a drogue-only
    tanker and vice versa.
    """

    BOOM = "boom"
    PROBE = "probe"

    @classmethod
    def from_data(cls, value: Optional[str]) -> Optional["AirRefuelType"]:
        if value is None or value == NO_AIR_REFUEL:
            return None
        return cls(value)


#: The ``air_refuel_type`` an airframe is authored with when DCS gives it no way
#: to take fuel in the air. Not a method, so it never adds tanker demand.
NO_AIR_REFUEL = "none"


@dataclass(frozen=True)
class RadioConfig:
    inter_flight: Optional[Radio]
    intra_flight: Optional[Radio]
    channel_allocator: Optional[RadioChannelAllocator]
    channel_namer: Type[ChannelNamer]

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> RadioConfig:
        return RadioConfig(
            cls.make_radio(data.get("inter_flight", None)),
            cls.make_radio(data.get("intra_flight", None)),
            cls.make_allocator(data.get("channels", {})),
            cls.make_namer(data.get("channels", {})),
        )

    @classmethod
    def make_radio(cls, name: Optional[str]) -> Optional[Radio]:
        from game.radio.radios import get_radio

        if name is None:
            return None
        return get_radio(name)

    @classmethod
    def make_allocator(cls, data: dict[str, Any]) -> Optional[RadioChannelAllocator]:
        try:
            alloc_type = data["type"]
        except KeyError:
            return None
        allocator_type: Type[RadioChannelAllocator] = {
            "SCR-522": SCR522RadioChannelAllocator,
            "ARC-5": ARC5RadioChannelAllocator,
            "common": CommonRadioChannelAllocator,
            "farmer": FarmerRadioChannelAllocator,
            "noop": NoOpChannelAllocator,
            "viggen": ViggenRadioChannelAllocator,
        }[alloc_type]
        return allocator_type.from_cfg(data)

    @classmethod
    def make_namer(cls, config: dict[str, Any]) -> Type[ChannelNamer]:
        return {
            "SCR-522": SCR522ChannelNamer,
            "ARC-5": ARC5ChannelNamer,
            "default": ChannelNamer,
            "huey": HueyChannelNamer,
            "mirage": MirageChannelNamer,
            "mirage-f1ce": MirageF1CEChannelNamer,
            "single": SingleRadioChannelNamer,
            "tomcat": TomcatChannelNamer,
            "viggen": ViggenChannelNamer,
            "viper": ViperChannelNamer,
            "apache": ApacheChannelNamer,
            "a10c-legacy": LegacyWarthogChannelNamer,
            "a10c-ii": WarthogChannelNamer,
            "phantom": PhantomChannelNamer,
            "kiowa": KiowaChannelNamer,
            "fulcrum": FulcrumChannelNamer,
        }[config.get("namer", "default")]


@dataclass(frozen=True)
class PatrolConfig:
    altitude: Optional[Distance]
    speed: Optional[Speed]

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> PatrolConfig:
        altitude = data.get("altitude", None)
        speed = data.get("speed", None)
        return PatrolConfig(
            feet(altitude) if altitude is not None else None,
            knots(speed) if speed is not None else None,
        )


@dataclass(frozen=True)
class AltitudesConfig:
    cruise: Optional[Distance]
    combat: Optional[Distance]

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> AltitudesConfig:
        cruise = data.get("cruise", None)
        combat = data.get("combat", None)
        return AltitudesConfig(
            feet(cruise) if cruise is not None else None,
            feet(combat) if combat is not None else None,
        )


@dataclass(frozen=True)
class FuelConsumption:
    #: The estimated taxi fuel requirement, in pounds.
    taxi: int

    #: The estimated fuel consumption for a takeoff climb, in pounds per nautical mile.
    climb: float

    #: The estimated fuel consumption for cruising, in pounds per nautical mile.
    cruise: float

    #: The estimated fuel consumption for combat speeds, in pounds per nautical mile.
    combat: float

    #: The minimum amount of fuel that the aircraft should land with, in pounds. This is
    #: a reserve amount for landing delays or emergencies.
    min_safe: int

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> FuelConsumption:
        return FuelConsumption(
            int(data["taxi"]),
            float(data["climb_ppm"]),
            float(data["cruise_ppm"]),
            float(data["combat_ppm"]),
            int(data["min_safe"]),
        )


# pydcs default-task classes that mark an aircraft as a large, fuel-efficient
# "heavy" (transport / tanker / AWACS / recon). Heavies burn far less fuel per
# pound carried than combat jets, so the estimated fuel ladder gives them a much
# longer cruise endurance. See AircraftType.estimated_fuel_consumption.
_HEAVY_AIRFRAME_TASKS = frozenset({Transport, Refueling, AWACS, Reconnaissance})


# TODO: Split into PlaneType and HelicopterType?
@dataclass(frozen=True)
class AircraftType(UnitType[Type[FlyingType]]):
    carrier_capable: bool
    lha_capable: bool
    always_keeps_gun: bool

    # If true, the aircraft does not use the guns as the last resort weapons, but as a
    # main weapon. It'll RTB when it doesn't have gun ammo left.
    gunfighter: bool

    # UnitSystem to use for the kneeboard, defaults to Nautical (kt/nm/ft)
    kneeboard_units: UnitSystem

    # If true, kneeboards will display zulu times
    utc_kneeboard: bool

    max_group_size: int
    patrol_altitude: Optional[Distance]
    patrol_speed: Optional[Speed]

    #: Minutes a player needs on the ramp before taxi, if this airframe differs from
    #: the campaign-wide ``player_startup_time``. Taxi is NOT included -- that is
    #: ``estimate_ground_ops``, which varies by field, not by airframe.
    #: See docs/dev/design/retlab-startup-times-notes.md for where a value comes from.
    startup_minutes: Optional[int]

    cruise_altitude: Optional[Distance]
    combat_altitude: Optional[Distance]

    #: Cruise mach for this airframe, when it differs from the planner's flat
    #: default. Authored from measurement, never derived: store weight does not
    #: predict it. See docs/dev/design/retlab-cruise-mach-notes.md.
    cruise_mach: Optional[float]

    #: The maximum range between the origin airfield and the target for which the auto-
    #: planner will consider this aircraft usable for a mission.
    max_mission_range: Distance

    fuel_consumption: Optional[FuelConsumption]

    default_livery: Optional[str]

    intra_flight_radio: Optional[Radio]
    channel_allocator: Optional[RadioChannelAllocator]
    channel_namer: Type[ChannelNamer]

    # Logisitcs info
    # cabin_size defines how many troops can be loaded. 0 means the aircraft can not
    # transport any troops. Default for helos is 10, non helos will have 0.
    cabin_size: int
    # If the aircraft can carry crates can_carry_crates should be set to true which
    # will be set to true for helos by default
    can_carry_crates: bool

    # Set to True when aircraft mounts a targeting pod by default i.e. the pod does
    # not take up a weapons station. If True, do not replace LGBs with dumb bombs
    # when no TGP is mounted on any station.
    has_built_in_target_pod: bool

    # Legacy EW capability metadata retained for third-party YAML compatibility.
    # The retired ewrj plugin used this to grant generic defensive aircraft jamming.
    has_built_in_ecm: bool

    # Legacy EW capability metadata retained for third-party YAML compatibility.
    # RetLab EW model is now the C-130J JAMMING flight + c130j plugin.
    has_built_in_jamming: bool

    task_priorities: dict[FlightType, int]
    laser_code_configs: list[LaserCodeConfig]

    use_f15e_waypoint_names: bool

    #: Tasks the aircraft is capable of but that are not auto-assignable by default
    #: (the squadron's mission-type checkbox starts unchecked). Still selectable
    #: manually. Each must also appear in ``tasks`` to supply its priority.
    secondary_tasks: frozenset[FlightType] = frozenset()

    #: Air-to-air refueling method this aircraft uses as a *receiver*. ``None`` leaves
    #: it unspecified, which is treated permissively (compatible with any tanker) so
    #: untagged aircraft behave exactly as before.
    air_refuel_type: Optional[AirRefuelType] = None

    #: Authored ``air_refuel_type: none``: no tanker serves this airframe. Unset
    #: was read as "takes any tanker", which sent a Su-25 to an IL-78 track.
    cannot_air_refuel: bool = False

    #: Refueling methods this aircraft provides as a *tanker*. Empty leaves it
    #: unspecified/permissive (can service any receiver), preserving legacy behavior.
    tanker_refuel_types: frozenset[AirRefuelType] = frozenset()

    #: Whether this tanker can refuel helicopters / slow receivers (e.g. the KC-130's
    #: low-and-slow drogue). Only consulted when both sides are tagged.
    tanker_refuels_helicopters: bool = False

    #: Date gate for era-specific payload-editor properties (e.g. the helmet-mounted
    #: cueing selection), built from the aircraft data file's
    #: ``date_gated_properties`` block. Empty (gates nothing) for the many airframes
    #: that declare no block.
    property_date_gate: PropertyDateGate = PropertyDateGate()

    #: Year this airframe's tactical datalink entered service, from the data file's
    #: ``datalink_introduced``. ``None`` (the default, and the case for most
    #: airframes) means "no date known", which the era gate treats permissively --
    #: exactly the pre-2026-08-16 behaviour. pydcs's own ``eplrs`` flag says only
    #: that DCS lets you tick the box, and it is true for the B-47 and the OV-10A,
    #: so it cannot answer the era question on its own. See
    #: docs/dev/design/retlab-datalink-era-notes.md.
    datalink_introduced: Optional[int] = None

    #: Lift slots this airframe can carry on a ground-unit transfer, from the
    #: data file's ``airlift_capacity``. One slot is about seven tonnes; see
    #: game/data/airliftcapacity.py for the anchor and the cargo costs. ``None``
    #: (the default, and the case for every airframe that is not a transport)
    #: falls back to the pre-2026-08-26 constant. Deliberately NOT ``cabin_size``
    #: -- that counts CTLD infantry seats and is clamped for gameplay.
    airlift_capacity: Optional[int] = None

    #: The SEAD escort weapon only reaches short-range air defence (the AV-8B's
    #: Sidearm), so with ``front_line_sead_escort`` on it escorts front-line and
    #: helicopter-led packages only. Test 37: four such escorts went deep, fired
    #: nothing, and one pair died to the SA-11 it was meant to cover.
    sead_escort_front_line_only: bool = False

    _by_name: ClassVar[dict[str, AircraftType]] = {}
    _by_unit_type: ClassVar[dict[type[FlyingType], list[AircraftType]]] = defaultdict(
        list
    )

    def __setstate__(self, state: dict[str, Any]) -> None:
        # Save compat: the `name` field has been renamed `variant_id`.
        if "name" in state:
            state["variant_id"] = state.pop("name")

        # Update any existing models with new data on load.
        updated = AircraftType.named(state["variant_id"])
        self.__dict__.update(updated.__dict__)

    def __post_init__(self) -> None:
        enrich = {}
        if FlightType.SEAD_SWEEP not in self.task_priorities:
            if (value := self.task_priorities.get(FlightType.SEAD)) or (
                value := self.task_priorities.get(FlightType.SEAD_ESCORT)
            ):
                enrich[FlightType.SEAD_SWEEP] = value

        # Strategic bombers (B-1/B-52/Tu-160/...) hold a CAS/BAI priority only for
        # dropping on *called* coordinates. They must not inherit the
        # roam-and-self-acquire Armed Recon role -- neither auto-assigned nor manually
        # selectable -- so skip the CAS->Armed Recon derivation for them (and strip any
        # value get_task_priorities() already derived, below). They never author Armed
        # Recon in `tasks:`, so dropping it is safe.
        is_heavy_bomber = self.dcs_unit_type.id in HEAVY_BOMBER_DCS_IDS
        # Helicopters are not derived either: Armed Recon targets control points and
        # supply corridors theatre-wide, and a Huey hunting a FOB two hours away at
        # 200 ft is what that produced (Yankee Station, 2026-09-16, DM call). A helo
        # that should sweep must author `Armed Recon:` itself.
        if (
            FlightType.ARMED_RECON not in self.task_priorities
            and not is_heavy_bomber
            and not self.helicopter
        ):
            if (value := self.task_priorities.get(FlightType.CAS)) or (
                value := self.task_priorities.get(FlightType.BAI)
            ):
                enrich[FlightType.ARMED_RECON] = value

        if FlightType.RECOVERY not in self.task_priorities:
            if (
                value := self.task_priorities.get(FlightType.REFUELING)
            ) and self.carrier_capable is True:
                enrich[FlightType.RECOVERY] = value

        self.task_priorities.update(enrich)

        if is_heavy_bomber:
            # get_task_priorities() runs before this hook and may have already derived
            # Armed Recon from the bomber's CAS/BAI priority; strip it so a strategic
            # bomber carries no Armed Recon capability at all.
            self.task_priorities.pop(FlightType.ARMED_RECON, None)
            # Same reasoning one step further: CAS is troops-in-contact at the FLOT,
            # which is not a called-coordinate drop. A B-52 fragged onto a front line
            # is a danger-close carpet (brady.retribution, 2026-08-17). BAI -- the
            # interdiction lane behind the lines -- is untouched, and so is the §32
            # Arc Light carpet, which rides a Strike target.
            self.task_priorities.pop(FlightType.CAS, None)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, AircraftType) and self.variant_id == other.variant_id

    @classmethod
    def register(cls, unit_type: AircraftType) -> None:
        cls._by_name[unit_type.variant_id] = unit_type
        cls._by_unit_type[unit_type.dcs_unit_type].append(unit_type)

    @property
    def flyable(self) -> bool:
        return self.dcs_unit_type.flyable

    @property
    def helicopter(self) -> bool:
        return self.dcs_unit_type.helicopter

    @property
    def max_fuel(self) -> float:
        return self.dcs_unit_type.fuel_max

    @property
    def _is_heavy_airframe(self) -> bool:
        """True for large, fuel-efficient airframes (transports/tankers/AWACS/recon
        and big bombers), which get a much longer estimated cruise endurance than
        combat jets. Detected by the pydcs default task or, as a fallback, by airframe
        length (every flyable fighter/attack jet is well under 28 m)."""
        if self.dcs_unit_type.task_default in _HEAVY_AIRFRAME_TASKS:
            return True
        return getattr(self.dcs_unit_type, "length", 0.0) >= 28.0

    @cached_property
    def estimated_fuel_consumption(self) -> Optional[FuelConsumption]:
        """A rough FuelConsumption synthesised from internal fuel capacity, for the
        many airframes that ship no hand-measured ``fuel:`` data block.

        Used **only** to draw the kneeboard fuel ladder / bingo estimate for player
        flights when measured data is absent -- it is deliberately *not* wired into
        ``fuel_consumption``, so the flight planner (tanker tasking) and the in-flight
        fuel sim keep using measured data only and gain no new blast radius.

        The model scales burn to the airframe's internal fuel by an assumed still-air
        cruise endurance (NM on a full internal load), bucketed helicopter /
        heavy-transport / combat; climb/combat are multiples of cruise. These are
        planning approximations, not measurements -- a real ``fuel:`` block always wins.

        **On the combat bucket's 700 NM, and why it is not the best-fitting number.**
        The error here is asymmetric. Over-estimating burn draws a pessimistic bingo
        ladder and frags a tanker that may not be needed -- annoying, safe.
        Under-estimating draws an optimistic one and frags nothing -- the jet lands dry.
        So the constant is chosen to stay on the conservative side, not to minimise
        average error.

        It was originally 520, matching the thirstiest reference then available (the
        F/A-18C, which implies 489 NM), so every unmeasured airframe was treated as a
        Hornet. That is safe but coarse: against the nine independent measured
        references now in the tree it overshot cruise burn by up to **140%** (the F-14
        and F-15C, which are far more efficient per pound than a Hornet).

        700 NM is the *median* implied endurance across those nine references
        (spread 489-1246 NM). It roughly halves the worst overshoot to ~78% while
        leaving 7 of 9 references on the conservative side. Fitting the centre instead
        (~875 NM) would cut worst error to ~42% but flip 6 of 9 to optimistic, which is
        the wrong direction for a planning aid -- do not "improve" it that way without a
        deliberate call. Capacity is a weak predictor and a single constant cannot do
        much better; ``max_range`` was tested as an alternative input and is worse
        (it is an authored tasking radius, not a physical one). The real fix is measured
        data -- see ``docs/modding/fuel-consumption-measurement.md``.

        The helicopter and heavy buckets are independent and untouched by the above; the
        heavy bucket remains calibrated against the C-130J (~16 ppm).
        """
        fuel_lbs = self.max_fuel * KG_TO_LBS
        if fuel_lbs <= 0:
            return None
        # (cruise endurance NM, climb x, combat x, taxi fraction, reserve fraction)
        if self.helicopter:
            cruise_nm, climb_x, combat_x, taxi_frac, reserve_frac = (
                280.0,
                1.3,
                1.2,
                0.004,
                0.12,
            )
        elif self._is_heavy_airframe:
            cruise_nm, climb_x, combat_x, taxi_frac, reserve_frac = (
                2700.0,
                1.5,
                1.2,
                0.005,
                0.05,
            )
        else:  # combat jets / attack / warbirds
            cruise_nm, climb_x, combat_x, taxi_frac, reserve_frac = (
                # Median implied endurance across the 9 measured references, chosen to
                # stay conservative rather than to fit best -- see the docstring.
                700.0,
                2.0,
                1.6,
                0.015,
                0.15,
            )
        cruise = fuel_lbs / cruise_nm
        return FuelConsumption(
            taxi=max(50, round(fuel_lbs * taxi_frac)),
            climb=round(cruise * climb_x, 1),
            cruise=round(cruise, 1),
            combat=round(cruise * combat_x, 1),
            min_safe=max(200, round(fuel_lbs * reserve_frac)),
        )

    @cached_property
    def max_speed(self) -> Speed:
        return kph(self.dcs_unit_type.max_speed)

    @cached_property
    def preferred_patrol_altitude(self) -> Distance:
        if self.patrol_altitude:
            return self.patrol_altitude
        else:
            return self.preferred_altitude(*PATROL_ALTITUDE_BAND_KFT, "patrol")

    def preferred_patrol_speed(self, altitude: Distance) -> Speed:
        """Preferred true airspeed when patrolling"""
        if self.patrol_speed is not None:
            return self.patrol_speed
        else:
            # Estimate based on max speed.
            max_speed = self.max_speed
            if max_speed > SPEED_OF_SOUND_AT_SEA_LEVEL * 1.6:
                # Fast airplanes, should manage pretty high patrol speed
                return (
                    Speed.from_mach(0.85, altitude)
                    if altitude.feet > 20000
                    else Speed.from_mach(0.7, altitude)
                )
            elif max_speed > SPEED_OF_SOUND_AT_SEA_LEVEL * 1.2:
                # Medium-fast like F/A-18C
                return (
                    Speed.from_mach(0.8, altitude)
                    if altitude.feet > 20000
                    else Speed.from_mach(0.65, altitude)
                )
            elif max_speed > SPEED_OF_SOUND_AT_SEA_LEVEL * 0.7:
                # Semi-fast like airliners or similar
                return (
                    Speed.from_mach(0.6, altitude)
                    if altitude.feet > 20000
                    else Speed.from_mach(0.5, altitude)
                )
            elif self.helicopter:
                return max_speed * 0.4
            else:
                # Slow like warbirds or attack planes
                # return 50% of max speed + 5% per 2k above 10k to maintain momentum
                return max_speed * min(
                    1.0,
                    0.5
                    + (
                        (((altitude.feet - 10000) / 2000) * 0.05)
                        if altitude.feet > 10000
                        else 0
                    ),
                )

    @cached_property
    def preferred_cruise_altitude(self) -> Distance:
        if self.cruise_altitude:
            return self.cruise_altitude
        else:
            return self.preferred_altitude(*CRUISE_ALTITUDE_BAND_KFT, "cruise")

    @cached_property
    def preferred_combat_altitude(self) -> Distance:
        if self.combat_altitude:
            return self.combat_altitude
        else:
            return self.preferred_altitude(*COMBAT_ALTITUDE_BAND_KFT, "combat")

    def preferred_altitude(self, low: int, high: int, type: str) -> Distance:
        # Estimate based on max speed.
        # Aircraft with max speed 600 kph will prefer low
        # Aircraft with max speed 2800 kph will prefer high
        altitude_for_lowest_speed = feet(low * 1000)
        altitude_for_highest_speed = feet(high * 1000)
        lowest_speed = kph(600)
        highest_speed = kph(2800)
        factor = (self.max_speed - lowest_speed).kph / (
            highest_speed - lowest_speed
        ).kph
        altitude = (
            altitude_for_lowest_speed
            + (altitude_for_highest_speed - altitude_for_lowest_speed) * factor
        )
        logging.debug(
            f"Preferred {type} altitude for {self.dcs_unit_type.id}: {altitude.feet}"
        )
        rounded_altitude = feet(round(1000 * round(altitude.feet / 1000)))
        return max(
            altitude_for_lowest_speed,
            min(altitude_for_highest_speed, rounded_altitude),
        )

    def alloc_flight_radio(self, radio_registry: RadioRegistry) -> RadioFrequency:
        from game.radio.radios import ChannelInUseError, kHz

        if self.intra_flight_radio is not None:
            return radio_registry.alloc_for_radio(self.intra_flight_radio)

        # The default radio frequency is set in megahertz. For some aircraft, it is a
        # floating point value. For all current aircraft, adjusting to kilohertz will be
        # sufficient to convert to an integer.
        in_khz = float(self.dcs_unit_type.radio_frequency) * 1000
        if not in_khz.is_integer():
            logging.warning(
                f"Found unexpected sub-kHz default radio for {self}: {in_khz} kHz. "
                "Truncating to integer. The truncated frequency may not be valid for "
                "the aircraft."
            )

        freq = kHz(int(in_khz))
        try:
            radio_registry.reserve(freq)
        except ChannelInUseError:
            pass
        return freq

    def assign_channels_for_flight(
        self, flight: FlightData, mission_data: MissionData
    ) -> None:
        if self.channel_allocator is not None:
            self.channel_allocator.assign_channels_for_flight(flight, mission_data)

    def channel_name(self, radio_id: int, channel_id: int) -> str:
        return self.channel_namer.channel_name(radio_id, channel_id)

    @cached_property
    def laser_code_prop_ids(self) -> set[str]:
        laser_code_props: set[str] = set()
        for laser_code_config in self.laser_code_configs:
            laser_code_props.update(laser_code_config.iter_prop_ids())
        return laser_code_props

    def iter_props(self) -> Iterator[UnitPropertyDescription]:
        yield from self.dcs_unit_type.properties.values()

    def should_show_prop(self, prop_id: str) -> bool:
        return prop_id not in self.laser_code_prop_ids

    def capable_of(self, task: FlightType) -> bool:
        return task in self.task_priorities

    def can_refuel_from(self, tanker: AircraftType) -> bool:
        """Whether this aircraft (as a receiver) can take fuel from ``tanker``.

        Never for a receiver authored ``air_refuel_type: none``. Otherwise
        permissive when either side is untagged so the restriction is opt-in and never
        regresses existing campaigns: a receiver with no ``air_refuel_type``, or a
        tanker that advertises no ``tanker_refuel_types``, is always compatible. Once
        both are tagged, the boom/probe methods must match, and a helicopter receiver
        additionally requires a tanker flagged ``tanker_refuels_helicopters``.
        """
        if self.cannot_air_refuel:
            return False
        if self.air_refuel_type is None:
            return True
        if not tanker.tanker_refuel_types:
            return True
        if self.air_refuel_type not in tanker.tanker_refuel_types:
            return False
        if self.helicopter and not tanker.tanker_refuels_helicopters:
            return False
        return True

    def task_priority(self, task: FlightType) -> int:
        return self.task_priorities[task]

    @staticmethod
    def _migrator() -> Dict[str, str]:
        return {
            "F-15E Strike Eagle (AI)": "F-15E Strike Eagle",
            "[CH] Tu-95MSM": "Tu-95MS Bear-H",
            "[CH] Mi-28N AH": "Mi-28N Havoc",
            # The stock AI-only C-130 transport was retired in favor of the
            # player-flyable Airplane Simulation Company C-130J-30 (the DCS AI flies
            # it too), so in-progress campaigns with a C-130 squadron resolve to the
            # J-30 instead of bricking on load. The KC-130/KC-130J tankers stay.
            "C-130": "C-130J-30",
            # Hand-authored factions often name the J-30 by its full DCS module
            # title; alias it so the faction doesn't fail to load on that string.
            "C-130J-30 Super Hercules": "C-130J-30",
        }

    @classmethod
    def named(cls, name: str) -> AircraftType:
        if not cls._loaded:
            cls._load_all()
        return cls._by_name[cls._migrator().get(name, name)]

    @classmethod
    def for_dcs_type(cls, dcs_unit_type: Type[FlyingType]) -> Iterator[AircraftType]:
        if not cls._loaded:
            cls._load_all()
        yield from cls._by_unit_type[dcs_unit_type]

    @classmethod
    def iter_all(cls) -> Iterator[AircraftType]:
        if not cls._loaded:
            cls._load_all()
        yield from cls._by_name.values()

    @classmethod
    @cache
    def priority_list_for_task(cls, task: FlightType) -> list[AircraftType]:
        capable = []
        for aircraft in cls.iter_all():
            if aircraft.capable_of(task):
                capable.append(aircraft)
        return list(reversed(sorted(capable, key=lambda a: a.task_priority(task))))

    def iter_task_capabilities(self) -> Iterator[FlightType]:
        yield from self.task_priorities

    @staticmethod
    def each_dcs_type() -> Iterator[Type[FlyingType]]:
        yield from helicopter_map.values()
        yield from plane_map.values()

    @staticmethod
    def _set_props_overrides(
        config: Dict[str, Any], aircraft: Type[FlyingType]
    ) -> None:
        if aircraft.property_defaults is None:
            logging.warning(
                f"'{aircraft.id}' attempted to set default prop that does not exist."
            )
        else:
            for k in config:
                if k in aircraft.property_defaults:
                    aircraft.property_defaults[k] = config[k]
                else:
                    logging.warning(
                        f"'{aircraft.id}' attempted to set default prop '{k}' that does not exist"
                    )

    @classmethod
    def _data_directory(cls) -> Path:
        return Path("resources/units/aircraft")

    @classmethod
    def _variant_from_dict(
        cls, aircraft: Type[FlyingType], variant_id: str, data: dict[str, Any]
    ) -> AircraftType:
        try:
            price = data["price"]
        except KeyError as ex:
            raise KeyError(f"Missing required price field") from ex

        radio_config = RadioConfig.from_data(data.get("radios", {}))
        patrol_config = PatrolConfig.from_data(data.get("patrol", {}))
        altitudes_config = AltitudesConfig.from_data(data.get("altitudes", {}))

        try:
            mission_range = nautical_miles(int(data["max_range"]))
        except (KeyError, ValueError):
            mission_range = (
                nautical_miles(50) if aircraft.helicopter else nautical_miles(150)
            )
            logging.warning(
                f"{variant_id} does not specify a max_range. Defaulting to "
                f"{mission_range.nautical_miles}NM"
            )

        fuel_data = data.get("fuel")
        if fuel_data is not None:
            fuel_consumption: Optional[FuelConsumption] = FuelConsumption.from_data(
                fuel_data
            )
        else:
            fuel_consumption = None

        try:
            introduction = data["introduced"]
            if introduction is None:
                introduction = "N/A"
        except KeyError:
            introduction = "No data."

        units_data = data.get("kneeboard_units", "nautical").lower()
        units: UnitSystem = NauticalUnits()
        if units_data == "imperial":
            units = ImperialUnits()
        if units_data == "metric":
            units = MetricUnits()

        class_name = data.get("class")
        unit_class = UnitClass.PLANE if class_name is None else UnitClass(class_name)

        prop_overrides = data.get("default_overrides")
        if prop_overrides is not None:
            cls._set_props_overrides(prop_overrides, aircraft)

        cabin_size = data.get("cabin_size", 10 if aircraft.helicopter else 0)
        task_priorities = cls.get_task_priorities(data, aircraft, cabin_size)
        secondary_tasks = frozenset(
            FlightType(t) for t in data.get("secondary_tasks", [])
        )

        cls._custom_weapon_injections(aircraft, data)
        cls._user_weapon_injections(aircraft)

        display_name = data.get("display_name", variant_id)
        return AircraftType(
            dcs_unit_type=aircraft,
            variant_id=variant_id,
            display_name=display_name,
            description=data.get(
                "description",
                f"No data. <a href=\"https://google.com/search?q=DCS+{display_name.replace(' ', '+')}\"><span style=\"color:#FFFFFF\">Google {display_name}</span></a>",
            ),
            year_introduced=introduction,
            country_of_origin=data.get("origin", "No data."),
            manufacturer=data.get("manufacturer", "No data."),
            role=data.get("role", "No data."),
            price=price,
            carrier_capable=data.get("carrier_capable", False),
            lha_capable=data.get("lha_capable", False),
            always_keeps_gun=data.get("always_keeps_gun", False),
            gunfighter=data.get("gunfighter", False),
            max_group_size=data.get("max_group_size", aircraft.group_size_max),
            patrol_altitude=patrol_config.altitude,
            patrol_speed=patrol_config.speed,
            startup_minutes=data.get("startup_minutes"),
            cruise_altitude=altitudes_config.cruise,
            combat_altitude=altitudes_config.combat,
            cruise_mach=data.get("cruise_mach"),
            max_mission_range=mission_range,
            fuel_consumption=fuel_consumption,
            default_livery=data.get("default_livery"),
            intra_flight_radio=radio_config.intra_flight,
            channel_allocator=radio_config.channel_allocator,
            channel_namer=radio_config.channel_namer,
            kneeboard_units=units,
            utc_kneeboard=data.get("utc_kneeboard", False),
            unit_class=unit_class,
            cabin_size=cabin_size,
            can_carry_crates=data.get("can_carry_crates", aircraft.helicopter),
            task_priorities=task_priorities,
            secondary_tasks=secondary_tasks,
            has_built_in_target_pod=data.get("has_built_in_target_pod", False),
            has_built_in_ecm=data.get("has_built_in_ecm", False),
            has_built_in_jamming=data.get("has_built_in_jamming", False),
            laser_code_configs=[
                LaserCodeConfig.from_yaml(d) for d in data.get("laser_codes", [])
            ],
            use_f15e_waypoint_names=data.get("use_f15e_waypoint_names", False),
            air_refuel_type=AirRefuelType.from_data(data.get("air_refuel_type")),
            cannot_air_refuel=data.get("air_refuel_type") == NO_AIR_REFUEL,
            tanker_refuel_types=frozenset(
                AirRefuelType(v) for v in data.get("tanker_refuel_types", [])
            ),
            tanker_refuels_helicopters=data.get("tanker_refuels_helicopters", False),
            property_date_gate=PropertyDateGate.from_data(
                data.get("date_gated_properties")
            ),
            datalink_introduced=cls._parse_datalink_introduced(data),
            airlift_capacity=cls._parse_airlift_capacity(data),
            sead_escort_front_line_only=bool(
                data.get("sead_escort_front_line_only", False)
            ),
        )

    @staticmethod
    def _parse_airlift_capacity(data: dict[str, Any]) -> Optional[int]:
        """The ``airlift_capacity`` in lift slots, or None when unauthored.

        A malformed or non-positive value is dropped with a warning rather
        than raising, matching ``_parse_datalink_introduced``: a typo in one
        unit file must not take the game down, and None restores the old
        constant. Zero is refused because it would mean "cannot airlift", a
        claim the transport task list already makes.
        """
        raw = data.get("airlift_capacity")
        if raw is None:
            return None
        try:
            capacity = int(raw)
        except (TypeError, ValueError):
            logging.warning(
                "Ignoring non-integer airlift_capacity %r in aircraft data", raw
            )
            return None
        if capacity < 1:
            logging.warning(
                "Ignoring non-positive airlift_capacity %r in aircraft data", raw
            )
            return None
        return capacity

    @staticmethod
    def _parse_datalink_introduced(data: dict[str, Any]) -> Optional[int]:
        """The ``datalink_introduced`` year, or None when the file omits it.

        A malformed value is dropped with a warning rather than raising: a typo
        in one unit file must not take the whole game down, and None simply
        means the era gate does not restrict this airframe.
        """
        raw = data.get("datalink_introduced")
        if raw is None:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            logging.warning(
                "Ignoring non-integer datalink_introduced %r in aircraft data", raw
            )
            return None

    @classmethod
    def get_task_priorities(
        cls,
        data: dict[str, Any],
        aircraft: Optional[Type[FlyingType]] = None,
        cabin_size: int = 0,
    ) -> dict[FlightType, int]:
        task_priorities: dict[FlightType, int] = {}
        for task_name, priority in data.get("tasks", {}).items():
            task_priorities[FlightType(task_name)] = priority
        if (
            FlightType.SEAD_SWEEP not in task_priorities
            and FlightType.SEAD in task_priorities
        ):
            task_priorities[FlightType.SEAD_SWEEP] = task_priorities[FlightType.SEAD]
        if (
            FlightType.ARMED_RECON not in task_priorities
            and data.get("class") != "Helicopter"
        ):
            if FlightType.CAS in task_priorities:
                task_priorities[FlightType.ARMED_RECON] = task_priorities[
                    FlightType.CAS
                ]
            elif FlightType.BAI in task_priorities:
                task_priorities[FlightType.ARMED_RECON] = task_priorities[
                    FlightType.BAI
                ]
        # Derive CSAR capability. Helicopters only: a CSAR aircraft has to actually
        # set down at an unprepared pickup site, and fixed-wing transports (the
        # C-130/Hercules mod included) cannot -- the DCS AI Land task is
        # helicopter-only, so they just orbit the pilot indefinitely. A positive
        # cabin size is also required, which skips zero-cabin attack/scout helos
        # like the OH-58D. An explicit per-aircraft `CSAR:` task entry always wins
        # over this derivation.
        if FlightType.CSAR not in task_priorities and cabin_size > 0:
            if aircraft is not None and aircraft.helicopter:
                if FlightType.AIR_ASSAULT in task_priorities:
                    task_priorities[FlightType.CSAR] = task_priorities[
                        FlightType.AIR_ASSAULT
                    ]
                elif FlightType.TRANSPORT in task_priorities:
                    task_priorities[FlightType.CSAR] = task_priorities[
                        FlightType.TRANSPORT
                    ]
                else:
                    task_priorities[FlightType.CSAR] = 50
        return task_priorities

    @staticmethod
    def _custom_weapon_injections(
        aircraft: Type[FlyingType], data: Dict[str, Any]
    ) -> None:
        if (wpn_injection := data.get("weapon_injections")) is not None:
            pylons = [
                v
                for v in aircraft.__dict__.values()
                if inspect.isclass(v) and v.__name__.startswith(f"Pylon")
            ]
            pylons.sort(key=lambda x: int(x.__name__.replace("Pylon", "")))
            for pylon_number, weapons in wpn_injection.items():
                for w in weapons:
                    weapon = weapon_ids[w]
                    pylon = [
                        pylon
                        for pylon in pylons
                        if int(pylon.__name__.replace("Pylon", "")) == pylon_number
                    ][0]
                    setattr(pylon, w, (pylon_number, weapon))

    @staticmethod
    def _user_weapon_injections(aircraft: Type[FlyingType]) -> None:
        data_path = user_custom_weapon_injections_dir() / f"{aircraft.id}.yaml"
        if not data_path.exists():
            return
        with data_path.open(encoding="utf-8") as data_file:
            data = yaml.safe_load(data_file)
        AircraftType._custom_weapon_injections(aircraft, data)

    def __hash__(self) -> int:
        return hash(self.variant_id)
