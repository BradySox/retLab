"""The tanker on-station setting goes to 300 minutes; the recovery station does not.

A theater tanker that spawns on its track skips the flight out, so it can hold
station longer on the same fuel (DM call 2026-10-10). The carrier recovery
tanker reads the same setting for where its station sits, 20 kt times the
minutes, and keeps the old 150-minute bound.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import timedelta
from types import SimpleNamespace

import pytest

from game.ato.flightplans.shiprecoverytanker import (
    RECOVERY_STATION_TIME_CAP,
    recovery_station_time,
)
from game.settings import Settings
from game.settings.optiondescription import SETTING_DESCRIPTION_KEY


def _option(name: str) -> object:
    field = next(f for f in fields(Settings) if f.name == name)
    return field.metadata[SETTING_DESCRIPTION_KEY]


def test_the_tanker_limit_matches_the_awacs_limit() -> None:
    tanker = _option("desired_tanker_on_station_time")
    awacs = _option("desired_awacs_mission_duration")
    assert tanker.max == 300  # type: ignore[attr-defined]
    assert tanker.max == awacs.max  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "minutes,expected", [(60, 60), (120, 120), (150, 150), (151, 150), (300, 150)]
)
def test_the_recovery_station_keeps_the_old_bound(minutes: int, expected: int) -> None:
    settings = SimpleNamespace(
        desired_tanker_on_station_time=timedelta(minutes=minutes)
    )
    assert recovery_station_time(settings) == timedelta(minutes=expected)
    assert RECOVERY_STATION_TIME_CAP == timedelta(minutes=150)
