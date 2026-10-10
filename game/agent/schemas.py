"""What the outside AI posts to plan red, and what it gets back.

Ported from juanjux/dcs-escalation `game/agent/schemas.py` (LGPL-3), cut to the
actions of §109 stage 2a. Design note: docs/dev/design/retlab-llm-opfor-notes.md.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from game.agent import views


class FlightSpec(BaseModel):
    task: str  # a FlightType name or value: STRIKE, DEAD, BARCAP, "Escort", ...
    count: int = 2  # capped at the airframe's max group size and at what is free
    escort: Optional[str] = None  # air / sead / refuel: pruned when not needed
    squadron_id: Optional[str] = None  # only this squadron may fill the flight
    tot_offset_min: Optional[float] = None  # vs the package TOT; negative = ahead


class PackageSpec(BaseModel):
    target_id: str  # a target, control point or front id from turn_context
    flights: list[FlightSpec]
    tot_minutes: Optional[int] = None  # minutes after mission start; omit for ASAP
    ignore_range: bool = False  # plan past the auto-planner's range limit


class DroppedFlight(BaseModel):
    flight: str
    reason: str


class CreateResult(BaseModel):
    ok: bool
    target: str
    error: Optional[str] = None
    package: Optional[views.PackageView] = None
    dropped: Optional[list[DroppedFlight]] = None  # flights left out: always read it
    idle_flyable_remaining: Optional[int] = None


class EvaluateResult(BaseModel):
    """A package planned and rolled back: what it would be, committed to nothing."""

    ok: bool
    target: str
    error: Optional[str] = None
    package: Optional[views.PackageView] = None
    tot_minutes_into_mission: Optional[int] = None
    mission_window_min: Optional[int] = None
    within_window: Optional[bool] = None


class PackageCheck(BaseModel):
    index: int
    target: str
    tot: Optional[str] = None
    tot_minutes_into_mission: Optional[int] = None
    within_window: Optional[bool] = None
    uncrewed: Optional[int] = None
    earliest_tot_minutes: Optional[int] = None  # only when the TOT cannot be made
    starts_mission_early_min: Optional[int] = None  # §104; the TOT is still made


class ValidateResult(BaseModel):
    ok: bool  # every package crewed and able to make its TOT
    mission_window_min: int
    packages: list[PackageCheck]
    issues: Optional[list[str]] = None  # what makes ok false
    notes: Optional[list[str]] = None  # worth knowing; never makes ok false


class OpResult(BaseModel):
    ok: bool
    detail: Optional[str] = None
    error: Optional[str] = None


class CreatePackagesRequest(BaseModel):
    side: str = "red"
    packages: list[PackageSpec]


class EvaluatePackageRequest(BaseModel):
    side: str = "red"
    package: PackageSpec


class PackageTotRequest(BaseModel):
    side: str = "red"
    tot_minutes: Optional[int] = None  # null resets to ASAP


class BuyAircraftRequest(BaseModel):
    side: str = "red"
    squadron_id: str
    quantity: int = 1


class BuyGroundRequest(BaseModel):
    side: str = "red"
    cp_id: str
    unit_name: str
    quantity: int = 1


class StanceRequest(BaseModel):
    side: str = "red"
    friendly_cp_id: str
    enemy_cp_id: str
    stance: str


class NotesRequest(BaseModel):
    notes: dict[str, str]
