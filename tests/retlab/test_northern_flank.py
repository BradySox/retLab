"""Kola - Northern Flank 1985 laydown guards.

RetLab's first campaign on the Kola map: the 1985 northern flank, fought on the
one coast road from Narvik to Murmansk and on the sea beside it, with Sweden and
Finland out of the war. The laydown is forked from Starfire's Able Archer 83 by
``tools/build_northern_flank_miz.py``; Able Archer still ships unchanged.

What these pin is what fails silently:

* a field that slips back in on neutral soil makes Sweden or Finland a
  belligerent, and §98 stops standing their border SAMs;
* DCS stands are nested, so a base's slot count is not the constraint (Bodo has
  94 stands and four that take a tanker; Luostari has 27 and none takes a jet);
* a squadron whose airframe needs a mod is dropped without a word, and this
  campaign promises stock units only.

Validated at ``load_theater`` depth, the fork's campaign-test convention.
Design note: docs/dev/design/retlab-northern-flank-campaign-notes.md
"""

from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest
import yaml
from dcs.mission import Mission
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon

from game import persistency
from game.campaignloader.campaign import Campaign
from game.dcs.aircrafttype import AircraftType
from game.factions import FACTIONS
from game.theater import ConflictTheater, ParkingType
from game.theater.controlpoint import Carrier
from game.theater.start_generator import ModSettings

YAML = Path("resources/campaigns/northern_flank_1985.yaml")
MIZ = Path("resources/campaigns/northern_flank_1985.miz")
ABLE_ARCHER = Path("resources/campaigns/exercise_able_archer.yaml")
BORDERS = Path("resources/borders/kola.yaml")

BLUE_FIELDS = {"Bodo", "Evenes", "Andoya", "Bardufoss"}
CARRIER = "Blue-CV"
RED_FIELDS = {
    "Alta",
    "Banak",
    "Kirkenes",
    "Koshka Yavr",
    "Severomorsk-1",
    "Olenya",
    "Monchegorsk",
}
NEUTRAL_COUNTRIES = {"Sweden", "Finland"}

#: The road, end to end, and the sea lanes either side of it.
ROADS = {
    frozenset(pair)
    for pair in (
        ("Evenes", "Bardufoss"),
        ("Bardufoss", "Alta"),
        ("Alta", "Banak"),
        ("Banak", "Kirkenes"),
        ("Kirkenes", "Koshka Yavr"),
        ("Koshka Yavr", "Severomorsk-1"),
        ("Severomorsk-1", "Olenya"),
        ("Olenya", "Monchegorsk"),
    )
}
SEA_LANES = {
    frozenset(pair)
    for pair in (
        ("Bodo", "Evenes"),
        ("Bodo", "Andoya"),
        ("Severomorsk-1", "Kirkenes"),
        ("Kirkenes", "Banak"),
    )
}

#: No squadron preset exists for these airframes anywhere in `resources/squadrons`
#: (the second MiG-23MLD regiment has used the only Soviet one), so the squadron
#: is named by its type. A content gap in the repo, listed so the guard below
#: stays meaningful.
NO_PRESET_EXISTS = {
    "MiG-23MLD Flogger-K",
    "MiG-25PD Foxbat-E",
    "MiG-25RBT Foxbat-B",
    "MiG-31 Foxhound",
    "Tu-142 Bear-F",
}


@pytest.fixture(scope="module")
def loaded(tmp_path_factory: Any) -> tuple[Campaign, ConflictTheater]:
    persistency.setup(str(tmp_path_factory.mktemp("northern-flank")), False, 0)
    campaign = Campaign.from_file(YAML)
    return campaign, campaign.load_theater(campaign.advanced_iads)


@pytest.fixture(scope="module")
def neutral_soil() -> list[Polygon]:
    data = yaml.safe_load(BORDERS.read_text(encoding="utf-8"))
    return [
        Polygon(zone["border"])
        for zone in data["zones"]
        if zone["country"] in NEUTRAL_COUNTRIES
    ]


def test_it_is_its_own_campaign_and_able_archer_is_untouched(
    loaded: tuple[Campaign, ConflictTheater],
) -> None:
    campaign, _ = loaded
    assert campaign.name == "Kola - Northern Flank 1985"
    source = Campaign.from_file(ABLE_ARCHER)
    assert source.name == "Kola Peninsula - Able Archer 83"
    assert source.recommended_start_date != campaign.recommended_start_date
    assert source.recommended_player_faction != campaign.recommended_player_faction
    assert source.recommended_enemy_faction != campaign.recommended_enemy_faction


def test_the_era_and_the_season(loaded: tuple[Campaign, ConflictTheater]) -> None:
    campaign, _ = loaded
    start = campaign.recommended_start_date
    assert start is not None
    # September: about 14 hours of daylight at 69 N. A winter start is polar night.
    assert (start.year, start.month) == (1985, 9)


@pytest.mark.parametrize(
    "name", ["NATO Northern Flank 1985", "USSR Northern Fleet 1985"]
)
def test_both_factions_are_stock_dcs(name: str, tmp_path: Path) -> None:
    """A mod-gated unit is stripped at New Game, and its squadron with it."""
    persistency.setup(str(tmp_path), False, 0)
    import copy

    faction = copy.deepcopy(FACTIONS[name])
    aircraft = {a.display_name for a in faction.all_aircrafts}
    ships = {s.display_name for s in faction.naval_units}
    presets = {g.name for g in faction.preset_groups}
    faction.apply_mod_settings(ModSettings())  # every mod toggle off
    assert {a.display_name for a in faction.all_aircrafts} == aircraft
    assert {s.display_name for s in faction.naval_units} == ships
    assert {g.name for g in faction.preset_groups} == presets


def test_the_sides_hold_the_road_and_nobody_else_holds_anything(
    loaded: tuple[Campaign, ConflictTheater],
) -> None:
    _, theater = loaded
    blue = {cp.name for cp in theater.controlpoints if cp.starting_coalition.is_blue}
    red = {cp.name for cp in theater.controlpoints if cp.starting_coalition.is_red}
    carriers = [cp for cp in theater.controlpoints if isinstance(cp, Carrier)]
    assert [cp.name for cp in carriers] == [CARRIER]
    assert blue == BLUE_FIELDS | {CARRIER}
    assert red == RED_FIELDS
    # Nothing else: a third category here is a field that came back neutral-held.
    assert len(theater.controlpoints) == len(blue) + len(red)


def test_sweden_and_finland_hold_nothing(
    loaded: tuple[Campaign, ConflictTheater], neutral_soil: list[Polygon]
) -> None:
    """§98 reads a country with no airfield as uninvolved. One base ends that."""
    _, theater = loaded

    def on_neutral_soil(x: float, y: float) -> bool:
        return any(zone.contains(ShapelyPoint(x, y)) for zone in neutral_soil)

    for cp in theater.controlpoints:
        assert not on_neutral_soil(cp.position.x, cp.position.y), cp.name
        for name, locations in vars(cp.preset_locations).items():
            for location in locations:
                position = getattr(location, "position", location)
                assert not on_neutral_soil(
                    position.x, position.y
                ), f"{cp.name}: a {name} marker stands in Sweden or Finland"


def test_the_road_and_the_sea_lanes(loaded: tuple[Campaign, ConflictTheater]) -> None:
    _, theater = loaded
    roads = set()
    lanes = set()
    for cp in theater.controlpoints:
        roads |= {frozenset((cp.name, other.name)) for other in cp.connected_points}
        lanes |= {frozenset((cp.name, other.name)) for other in cp.shipping_lanes}
    assert roads == ROADS
    assert lanes == SEA_LANES
    # One front, and it is the Lyngen position.
    opposed = [
        pair
        for pair in ROADS
        if len(
            {theater.control_point_named(n).starting_coalition.is_blue for n in pair}
        )
        == 2
    ]
    assert opposed == [frozenset(("Bardufoss", "Alta"))]


def test_the_patrol_range_reaches_across_the_front(
    loaded: tuple[Campaign, ConflictTheater],
) -> None:
    # A base is patrolled only when an enemy field is inside airbase_threat_range.
    # At the stock 100 NM neither side flew a land-base BARCAP here.
    campaign, theater = loaded
    patrol_range = campaign.settings["airbase_threat_range"]
    alta = theater.control_point_named("Alta")
    bardufoss = theater.control_point_named("Bardufoss")
    gap_nm = alta.position.distance_to_point(bardufoss.position) / 1852
    assert 100 < gap_nm < patrol_range
    # Every forward red field, so the rear interceptors have a station to fly to.
    for name in ("Banak", "Kirkenes", "Koshka Yavr"):
        field = theater.control_point_named(name)
        assert field.position.distance_to_point(bardufoss.position) / 1852 < (
            patrol_range
        )


def test_the_front_starts_at_the_lyngen_position(
    loaded: tuple[Campaign, ConflictTheater],
) -> None:
    campaign, theater = loaded
    assert campaign.data["control_point_strengths"] == {"Bardufoss": 0.3}
    assert theater.control_point_named("Bardufoss").base.strength == pytest.approx(0.3)


def test_no_base_oversubscribes_a_stand_class(
    loaded: tuple[Campaign, ConflictTheater],
) -> None:
    """Hall's condition over the nested stand classes (see test_iron_gate)."""
    campaign, theater = loaded
    config = campaign.load_air_wing_config(theater)
    for cp, squadrons in config.by_location.items():
        airport = getattr(cp, "airport", None)
        if airport is None:  # the carrier: one flat pool
            pool = cp.total_aircraft_parking(
                ParkingType(fixed_wing=True, fixed_wing_stol=True, rotary_wing=True)
            )
            assert sum(s.max_size for s in squadrons) <= pool, cp.name
            continue
        wanted: dict[int, int] = defaultdict(int)
        for squadron in squadrons:
            aircraft = AircraftType.named(
                squadron.aircraft_type or squadron.aircraft[0]
            )
            fits = len(airport.free_parking_slots(aircraft.dcs_unit_type))
            assert fits > 0, f"{cp.name}: no stand takes a {aircraft.display_name}"
            wanted[fits] += squadron.max_size
        assert sum(wanted.values()) <= len(airport.parking_slots), cp.name
        for capacity in sorted(wanted):
            needed = sum(n for fits, n in wanted.items() if fits <= capacity)
            assert needed <= capacity, (
                f"{cp.name}: {needed} aircraft need a stand of class {capacity} "
                f"or smaller, but only {capacity} such stands exist"
            )


def test_every_squadron_is_in_its_sides_faction(
    loaded: tuple[Campaign, ConflictTheater],
) -> None:
    """An airframe missing from the faction does not fail; it substitutes."""
    campaign, theater = loaded
    config = campaign.load_air_wing_config(theater)
    rosters = {
        True: FACTIONS[campaign.recommended_player_faction],
        False: FACTIONS[campaign.recommended_enemy_faction],
    }
    for cp, squadrons in config.by_location.items():
        fielded = {
            a.display_name for a in rosters[cp.starting_coalition.is_blue].all_aircrafts
        }
        for squadron in squadrons:
            kind = squadron.aircraft_type or squadron.aircraft[0]
            assert kind in fielded, f"{cp.name}: the faction has no {kind}"


def test_every_squadron_is_a_real_unit_where_one_exists(
    loaded: tuple[Campaign, ConflictTheater],
) -> None:
    presets: dict[str, set[str]] = defaultdict(set)
    for path in Path("resources/squadrons").rglob("*.yaml"):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if data and "name" in data and "aircraft" in data:
            presets[str(data["name"])].add(str(data["aircraft"]))

    campaign, theater = loaded
    config = campaign.load_air_wing_config(theater)
    for cp, squadrons in config.by_location.items():
        for squadron in squadrons:
            kind = squadron.aircraft_type or squadron.aircraft[0]
            for named in squadron.aircraft:
                if named == kind:
                    assert kind in NO_PRESET_EXISTS, (
                        f"{cp.name}: the {kind} squadron names its own type "
                        f"instead of a unit"
                    )
                    continue
                assert named in presets, f"{cp.name}: no preset named {named!r}"
                assert (
                    kind in presets[named]
                ), f"{cp.name}: preset {named!r} does not fly the {kind}"


def test_every_pinned_marker_exists(loaded: tuple[Campaign, ConflictTheater]) -> None:
    """A pin on a marker the miz does not carry is silently ignored."""
    campaign, _ = loaded
    mission = Mission()
    mission.load_file(str(MIZ))
    names = set()
    for coalition in mission.coalition.values():
        for country in coalition.countries.values():
            for group in list(country.vehicle_group) + list(country.ship_group):
                names.add(group.name)
    pins = campaign.data["ground_forces"]
    assert set(pins) <= names, set(pins) - names
    groups = {
        str(yaml.safe_load(p.read_text(encoding="utf-8"))["name"])
        for p in Path("resources/groups").glob("*.yaml")
    }
    assert set(pins.values()) <= groups, set(pins.values()) - groups


def test_the_carrier_is_the_one_the_yaml_names(
    loaded: tuple[Campaign, ConflictTheater],
) -> None:
    campaign, theater = loaded
    config = campaign.load_carrier_config()
    assert set(config.by_original_name) == {CARRIER}
    wing = campaign.load_air_wing_config(theater)
    carrier = theater.control_point_named(CARRIER)
    assert len(wing.by_location[carrier]) == 6
