"""Phase 4 data bridge — exports a compact JSON payload for the React/Three.js scene.

Keeps the frontend decoupled from pandas/CSV parsing entirely: one fetch,
one JSON blob, columnar per-oven so the browser never re-filters 48k rows
per animation frame — it just indexes `series[oven_id][field][stepIndex]`.

Design choices worth knowing:
- Ground truth (compoundrisk.scenarios) is intentionally NOT exported. A
  real safety tool has no oracle telling it which readings are "supposed"
  to be risky — surfacing that in the operator-facing UI would be a
  real-world-fidelity mistake, not a nice-to-have. It stays a backend-only
  evaluation artifact (Phase 3).
- risk_category is exported as an int code (0/1/2), not a repeated string,
  and boolean fields as 0/1 — both meaningfully shrink 48,240-row columns.
- Individual oven positions come from registry.build_oven_positions(),
  which shares its spacing formula with build_zone_layout()'s zone centers
  (see registry.py) so the scene's ovens and zone outlines can never drift
  apart from the backend's own layout math.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from compoundrisk import constants as C
from compoundrisk.registry import build_oven_positions, build_oven_registry, build_zone_layout
from compoundrisk.schemas import ExhausterStatus, RiskCategory, ZoneStatus

RISK_CATEGORY_CODE = {
    RiskCategory.LOW.value: 0,
    RiskCategory.MEDIUM.value: 1,
    RiskCategory.HIGH.value: 2,
}

ZONE_STATUS_CODE = {
    ZoneStatus.NORMAL.value: 0,
    ZoneStatus.RESTRICTED.value: 1,
}


def _round(values: np.ndarray, decimals: int) -> list[float]:
    return np.round(values.astype(float), decimals).tolist()


def _iso_utc(ts: pd.Timestamp) -> str:
    """SIM_START and permit times are naive (no tz) by construction — treat
    them as UTC explicitly so `new Date(...)` in the browser can't silently
    reinterpret them in the viewer's local timezone."""
    return pd.Timestamp(ts).isoformat() + "Z"


def _build_zone_status_series(zone_status_df: pd.DataFrame, timestamps: list) -> dict[str, list]:
    """zone_id -> [status code per step], same "index by step" convention as
    the per-oven `series` block."""
    n_steps = len(timestamps)
    out: dict[str, list] = {}
    for zid, group in zone_status_df.groupby("zone_id", sort=False):
        group = group.sort_values("timestamp")
        if len(group) != n_steps or not (group["timestamp"].to_numpy() == np.array(timestamps)).all():
            raise ValueError(f"{zid}: zone_status rows aren't aligned to the shared {n_steps}-step timeline")
        out[zid] = [ZONE_STATUS_CODE[s] for s in group["status"]]
    return out


def _build_worker_zone_series(occupancy_df: pd.DataFrame, timestamps: list) -> dict[str, list]:
    """worker_id -> [zone_id per step] — zone-level occupancy only, never a
    coordinate (see workers.py's module docstring for why)."""
    n_steps = len(timestamps)
    out: dict[str, list] = {}
    for wid, group in occupancy_df.groupby("worker_id", sort=False):
        group = group.sort_values("timestamp")
        if len(group) != n_steps or not (group["timestamp"].to_numpy() == np.array(timestamps)).all():
            raise ValueError(f"{wid}: worker occupancy rows aren't aligned to the shared {n_steps}-step timeline")
        out[wid] = group["zone_id"].tolist()
    return out


def _build_events(events_df: pd.DataFrame, timestamps: list) -> list[dict]:
    if events_df.empty:
        return []
    # Keyed on the integer nanosecond value rather than the Timestamp/
    # datetime64 object itself — events_df's timestamp column round-trips
    # through a DataFrame (pandas Timestamp) while `timestamps` comes
    # straight from .unique() (numpy datetime64); the two don't reliably
    # hash the same even when they compare equal.
    step_of = {pd.Timestamp(ts).value: i for i, ts in enumerate(timestamps)}
    return [
        {
            "event_id": row.event_id,
            "timestamp": _iso_utc(row.timestamp),
            "step": step_of[pd.Timestamp(row.timestamp).value],
            "worker_id": row.worker_id,
            "zone_id": row.zone_id,
            "event_type": row.event_type,
            "message": row.message,
        }
        for row in events_df.itertuples()
    ]


def build_payload(
    sensor_df: pd.DataFrame,
    permit_df: pd.DataFrame,
    risk_df: pd.DataFrame,
    worker_df: pd.DataFrame,
    occupancy_df: pd.DataFrame,
    events_df: pd.DataFrame,
    zone_status_df: pd.DataFrame,
) -> dict:
    oven_registry_df = build_oven_registry()
    oven_positions_df = build_oven_positions().merge(
        oven_registry_df[["oven_id", "volume_m3", "coal_charge_tons"]], on="oven_id", how="left"
    )
    zone_layout_df = build_zone_layout()

    merged = sensor_df.merge(
        risk_df[["oven_id", "timestamp", "risk_score", "risk_category", "compound_risk_flag", "risk_reason"]],
        on=["oven_id", "timestamp"],
        how="left",
    )
    if len(merged) != len(sensor_df):
        raise ValueError(
            f"sensor/risk merge changed row count ({len(sensor_df)} -> {len(merged)}) — "
            "risk_df must be exactly 1:1 with sensor_df on (oven_id, timestamp)."
        )

    timestamps = sorted(sensor_df["timestamp"].unique())
    n_steps = len(timestamps)

    series: dict[str, dict] = {}
    for oid, group in merged.groupby("oven_id", sort=False):
        group = group.sort_values("timestamp")
        if len(group) != n_steps or not (group["timestamp"].to_numpy() == np.array(timestamps)).all():
            raise ValueError(
                f"{oid}: sensor rows aren't aligned to the shared {n_steps}-step timeline — "
                "the frontend indexes every series by step index, so this would silently "
                "desync colors/values from the time scrubber."
            )
        series[oid] = {
            "risk_score": _round(group["risk_score"].to_numpy(), 3),
            "risk_category": [RISK_CATEGORY_CODE[c] for c in group["risk_category"]],
            "compound_risk_flag": group["compound_risk_flag"].astype(int).tolist(),
            "co_ppm": _round(group["co_ppm"].to_numpy(), 1),
            "lel_pct": _round(group["combustible_gas_pct_lel"].to_numpy(), 2),
            "gas_temp_c": _round(group["gas_temp_c"].to_numpy(), 1),
            "exhauster_fault": (group["exhauster_status"] == ExhausterStatus.FAULT.value).astype(int).tolist(),
            "maintenance_flag": group["maintenance_flag"].astype(int).tolist(),
            "risk_reason": group["risk_reason"].tolist(),
        }

    permits = [
        {
            "permit_id": row.permit_id,
            "oven_id": row.oven_id,
            "permit_type": row.permit_type,
            "status": row.status,
            "issued_time": _iso_utc(row.issued_time),
            "valid_until": _iso_utc(row.valid_until),
        }
        for row in permit_df.itertuples()
    ]

    return {
        "meta": {
            "battery_id": C.BATTERY_ID,
            "n_ovens": C.N_OVENS,
            "sim_start": _iso_utc(timestamps[0]),
            "interval_min": C.SAMPLE_INTERVAL_MIN,
            "n_steps": n_steps,
            "co_alert_ppm": C.CO_ALERT_PPM,
            "lel_alert_pct": C.LEL_CONFINED_ENTRY_PCT,
            "oven_spacing_m": 5.0,
            "risk_categories": ["low", "medium", "high"],
            "zone_statuses": ["normal", "restricted"],
        },
        "ovens": oven_positions_df.to_dict(orient="records"),
        "zones": zone_layout_df.to_dict(orient="records"),
        "permits": permits,
        "series": series,
        "workers": worker_df.to_dict(orient="records"),
        "zone_status": _build_zone_status_series(zone_status_df, timestamps),
        "worker_zones": _build_worker_zone_series(occupancy_df, timestamps),
        "events": _build_events(events_df, timestamps),
    }


def write_payload(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":")))
