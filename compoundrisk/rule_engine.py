"""Phase 2 — rule-based compound risk detection engine.

Implements the Section 3 rule EXACTLY as written, with no drift:

    Compound risk is flagged on an oven when:
      gas concentration exceeds the safe threshold (CO > 50 ppm OR %LEL > 5%)
      AND an active hot-work or confined-space permit exists on/near that oven
      AND a maintenance or exhauster-fault flag is active

All three boundary conditions matter and are covered by the confounder
scenarios in compoundrisk/scenarios.py:
  - strict ">" (not ">="), so a reading exactly at 50 ppm / 5% LEL does not
    trigger the gas condition
  - "active" permit status is checked, not just whether the timestamp falls
    within [issued_time, valid_until] — a permit left on file as 'closed'
    must not count even if its time window still overlaps (see C06)
  - only hot_work / confined_space_entry permits count; cold_work never
    satisfies the permit condition (see C05)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from compoundrisk import constants as C
from compoundrisk.schemas import ExhausterStatus, RiskCategory


def _permit_condition(sensor_df: pd.DataFrame, permit_df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Per-row (oven_id, timestamp): is a qualifying permit active, and if so which type."""
    relevant = permit_df[
        permit_df["permit_type"].isin(C.PERMIT_TYPES_THAT_COUNT) & (permit_df["status"] == "active")
    ]

    permit_active = pd.Series(False, index=sensor_df.index)
    permit_type_col = pd.Series(pd.NA, index=sensor_df.index, dtype=object)
    if relevant.empty:
        return permit_active, permit_type_col

    merged = (
        sensor_df[["oven_id", "timestamp"]]
        .reset_index()
        .merge(relevant[["oven_id", "permit_type", "issued_time", "valid_until"]], on="oven_id", how="inner")
    )
    within = merged[
        (merged["timestamp"] >= merged["issued_time"]) & (merged["timestamp"] <= merged["valid_until"])
    ]
    # If two qualifying permits overlap for the same oven/timestamp, report
    # the most recently issued one — deterministic and meaningful, instead
    # of whichever row order the merge happened to produce.
    within = within.sort_values("issued_time", ascending=False)
    first_match = within.groupby("index")["permit_type"].first()
    permit_active.loc[first_match.index] = True
    permit_type_col.loc[first_match.index] = first_match.values
    return permit_active, permit_type_col


def _risk_reason(row: pd.Series) -> str:
    parts = []
    if row["co_ppm"] > C.CO_ALERT_PPM:
        parts.append(f"CO {row['co_ppm']:.0f}ppm")
    if row["combustible_gas_pct_lel"] > C.LEL_CONFINED_ENTRY_PCT:
        parts.append(f"LEL {row['combustible_gas_pct_lel']:.1f}%")
    if row["permit_active"]:
        permit_label = str(row["permit_type"]).replace("_", "-")
        parts.append(f"active {permit_label} permit")
    if row["maintenance_flag"]:
        parts.append("maintenance flag active")
    if row["exhauster_status"] == ExhausterStatus.FAULT.value:
        parts.append("exhauster fault")
    if not parts:
        return "Normal operating parameters"
    return " + ".join(parts)


def run(sensor_df: pd.DataFrame, permit_df: pd.DataFrame) -> pd.DataFrame:
    """Section 4.5 — Risk Engine Output. One row per sensor reading."""
    df = sensor_df.copy()

    gas_condition = (df["co_ppm"] > C.CO_ALERT_PPM) | (df["combustible_gas_pct_lel"] > C.LEL_CONFINED_ENTRY_PCT)
    permit_active, permit_type = _permit_condition(df, permit_df)
    maintenance_condition = df["maintenance_flag"] | (df["exhauster_status"] == ExhausterStatus.FAULT.value)

    df["permit_active"] = permit_active
    df["permit_type"] = permit_type

    compound_flag = gas_condition & permit_active & maintenance_condition

    co_ratio = df["co_ppm"] / C.CO_ALERT_PPM
    lel_ratio = df["combustible_gas_pct_lel"] / C.LEL_CONFINED_ENTRY_PCT
    gas_ratio = np.maximum(co_ratio, lel_ratio)
    gas_component = np.where(gas_condition, np.minimum(1.5, gas_ratio) / 1.5, 0.0) * C.GAS_SCORE_WEIGHT
    permit_component = np.where(permit_active, C.PERMIT_SCORE_WEIGHT, 0.0)
    maintenance_component = np.where(maintenance_condition, C.MAINTENANCE_SCORE_WEIGHT, 0.0)

    risk_score = np.clip(gas_component + permit_component + maintenance_component, 0.0, 1.0)

    # Category is driven by which conditions are actually present, not by a
    # weighted-sum cutoff on risk_score: a cutoff can't reliably separate
    # "two factors, both maxed out" from "three factors, barely over
    # threshold" (0.5+0.25=0.75 vs 0.333+0.25+0.25=0.833 — too close for a
    # threshold to be robust). Any two-of-three confounder must never read
    # as "high", since that's the exact pattern the engine exists to reject.
    any_condition = gas_condition | permit_active | maintenance_condition
    risk_category = np.where(
        compound_flag,
        RiskCategory.HIGH.value,
        np.where(any_condition, RiskCategory.MEDIUM.value, RiskCategory.LOW.value),
    )

    df["gas_condition"] = gas_condition
    df["maintenance_condition"] = maintenance_condition
    df["compound_risk_flag"] = compound_flag
    df["risk_score"] = risk_score
    df["risk_category"] = risk_category
    df["risk_reason"] = df.apply(_risk_reason, axis=1)

    return df[
        [
            "oven_id",
            "timestamp",
            "risk_score",
            "risk_category",
            "compound_risk_flag",
            "risk_reason",
            "gas_condition",
            "permit_active",
            "maintenance_condition",
        ]
    ]
