"""Enum definitions for the four data tables in Section 4 of the spec.

Kept as plain str-Enums (not pydantic) so pandas can store/compare them as
ordinary strings without an extra dependency.
"""

from __future__ import annotations

from enum import Enum


class ExhausterStatus(str, Enum):
    NORMAL = "normal"
    FAULT = "fault"


class PermitType(str, Enum):
    HOT_WORK = "hot_work"
    CONFINED_SPACE_ENTRY = "confined_space_entry"
    COLD_WORK = "cold_work"


class PermitStatus(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"


class ZoneType(str, Enum):
    OVEN_BATTERY = "oven_battery"
    COAL_CHEMICAL_PLANT = "coal_chemical_plant"
    EXHAUSTER_HOUSE = "exhauster_house"


class RiskCategory(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ZoneStatus(str, Enum):
    NORMAL = "normal"
    RESTRICTED = "restricted"


class WorkerEventType(str, Enum):
    WARNING_ISSUED = "warning_issued"
    ENTRY_BLOCKED = "entry_blocked"
