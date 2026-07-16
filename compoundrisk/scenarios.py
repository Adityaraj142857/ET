"""Ground-truth risk scenarios injected into the synthetic simulation.

This module is the single source of truth for "what story are we telling."
Kept separate from simulate.py (which turns this story into noisy sensor
signals) so the intended ground truth can be read top-to-bottom and audited
without wading through numpy code.

Per Section 5, Phase 1: "inject 5-8 deliberate overlapping risk windows
(gas spike + open permit + maintenance flag, same oven, same time) as
ground truth." We inject 8 positive compound-risk windows, PLUS 6
confounder windows that each satisfy exactly two of the three Section-3
factors (or one). The confounders exist to prove the engine is actually
doing 3-way correlation rather than flagging on any single strong signal —
"individually-monitored sensors miss the compound pattern" only means
something if we also show two-out-of-three isn't enough.

All ovens/times below are distinct from one another (no oven is reused,
no two windows overlap in time on a shared zone's exhauster), so each
scenario can be evaluated independently.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GasSpike:
    driver: str  # "co", "lel", or "both"
    co_peak_ppm: float | None = None
    lel_peak_pct: float | None = None


@dataclass(frozen=True)
class PermitOverride:
    permit_type: str  # hot_work / confined_space_entry / cold_work
    status: str = "active"


@dataclass(frozen=True)
class RiskWindow:
    window_id: str
    oven_id: str
    start_hour: float
    end_hour: float
    kind: str  # "compound" (positive) or "confounder" (negative)
    should_flag: bool
    description: str
    gas: GasSpike | None = None
    permit: PermitOverride | None = None
    maintenance_flag: bool = False
    exhauster_fault: bool = False  # applied zone-wide for [start_hour, end_hour)


WINDOWS: list[RiskWindow] = [
    # ---- 8 compound-risk positives: gas + permit + (maintenance OR exhauster fault) ----
    RiskWindow(
        "W01", "B1-O05", 6, 7, "compound", True,
        "CO spike + active hot_work permit + maintenance flag",
        gas=GasSpike("co", co_peak_ppm=85),
        permit=PermitOverride("hot_work"),
        maintenance_flag=True,
    ),
    RiskWindow(
        "W02", "B1-O12", 14, 15, "compound", True,
        "LEL spike + active confined_space_entry permit + exhauster fault",
        gas=GasSpike("lel", lel_peak_pct=9.0),
        permit=PermitOverride("confined_space_entry"),
        exhauster_fault=True,
    ),
    RiskWindow(
        "W03", "B1-O20", 20, 21, "compound", True,
        "CO+LEL spike + active hot_work permit + maintenance flag",
        gas=GasSpike("both", co_peak_ppm=95.0, lel_peak_pct=8.0),
        permit=PermitOverride("hot_work"),
        maintenance_flag=True,
    ),
    RiskWindow(
        "W04", "B1-O28", 27, 28, "compound", True,
        "CO spike + active confined_space_entry permit + exhauster fault",
        gas=GasSpike("co", co_peak_ppm=78.0),
        permit=PermitOverride("confined_space_entry"),
        exhauster_fault=True,
    ),
    RiskWindow(
        "W05", "B1-O35", 33, 34, "compound", True,
        "LEL spike + active hot_work permit + maintenance flag",
        gas=GasSpike("lel", lel_peak_pct=11.0),
        permit=PermitOverride("hot_work"),
        maintenance_flag=True,
    ),
    RiskWindow(
        "W06", "B1-O44", 40, 41, "compound", True,
        "CO spike + active confined_space_entry permit + maintenance flag",
        gas=GasSpike("co", co_peak_ppm=70.0),
        permit=PermitOverride("confined_space_entry"),
        maintenance_flag=True,
    ),
    RiskWindow(
        "W07", "B1-O52", 47, 48, "compound", True,
        "CO+LEL spike + active hot_work permit + exhauster fault",
        gas=GasSpike("both", co_peak_ppm=110.0, lel_peak_pct=13.0),
        permit=PermitOverride("hot_work"),
        exhauster_fault=True,
    ),
    RiskWindow(
        "W08", "B1-O60", 53, 54, "compound", True,
        "LEL spike + active confined_space_entry permit + exhauster fault",
        gas=GasSpike("lel", lel_peak_pct=7.5),
        permit=PermitOverride("confined_space_entry"),
        exhauster_fault=True,
    ),
    # ---- 6 confounders: exactly one or two of three factors — must NOT flag ----
    RiskWindow(
        "C01", "B1-O08", 9, 10, "confounder", False,
        "Gas spike ONLY — no permit, no maintenance/exhauster fault",
        gas=GasSpike("co", co_peak_ppm=90.0),
    ),
    RiskWindow(
        "C02", "B1-O15", 17, 18, "confounder", False,
        "Active hot_work permit + maintenance flag, but gas stays at baseline",
        permit=PermitOverride("hot_work"),
        maintenance_flag=True,
    ),
    RiskWindow(
        "C03", "B1-O23", 23, 24, "confounder", False,
        "Exhauster fault ONLY (zone-wide) — no gas spike, no permit",
        exhauster_fault=True,
    ),
    RiskWindow(
        "C04", "B1-O31", 30, 31, "confounder", False,
        "CO spike + active hot_work permit, but NO maintenance flag / exhauster fault"
        " — proves two-of-three is not enough",
        gas=GasSpike("co", co_peak_ppm=88.0),
        permit=PermitOverride("hot_work"),
    ),
    RiskWindow(
        "C05", "B1-O38", 36, 37, "confounder", False,
        "CO spike + maintenance flag, but the on-file permit is cold_work (wrong type)",
        gas=GasSpike("co", co_peak_ppm=82.0),
        permit=PermitOverride("cold_work"),
        maintenance_flag=True,
    ),
    RiskWindow(
        "C06", "B1-O46", 43, 44, "confounder", False,
        "CO spike + maintenance flag + hot_work permit on file, but its status is"
        " 'closed' — proves the engine checks permit status, not just time bounds",
        gas=GasSpike("co", co_peak_ppm=91.0),
        permit=PermitOverride("hot_work", status="closed"),
        maintenance_flag=True,
    ),
]
