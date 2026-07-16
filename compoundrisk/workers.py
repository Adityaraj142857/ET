"""Zone-level worker occupancy + access-restriction events.

Deliberately zone-level only: a worker's state is `current_zone_id`,
updated periodically (every 15-30 simulated minutes), never a continuous
coordinate. This mirrors the ethical scoping already established in
Section 6 of coke_oven_risk_project_context.md ("No individual worker GPS
tracking... If an occupancy layer is added, it must be zone-level only") —
this module is that occupancy layer, not a location-tracking system.

Two things are computed here:
  1. zone_status: per (zone_id, timestamp), NORMAL or RESTRICTED. A zone is
     RESTRICTED when any oven inside it is at HIGH risk_category — category,
     not a raw risk_score cutoff, for the same reason rule_engine.py itself
     avoids a score cutoff for risk_category: a score can't reliably
     distinguish a genuine compound-risk case from a lower-scoring one, so
     category (which IS that determination) is the right "is this zone
     actually unsafe" signal.
  2. worker occupancy + events: each worker is periodically reassigned to a
     zone. A reassignment into a currently-RESTRICTED zone is blocked
     (entry_blocked event, worker stays put) rather than silently allowed.
     Separately, if a zone flips to RESTRICTED while a worker is already
     inside it, that worker is warned in place (warning_issued event).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from compoundrisk import constants as C
from compoundrisk.registry import oven_to_zone_map
from compoundrisk.schemas import RiskCategory, WorkerEventType, ZoneStatus, ZoneType

N_WORKERS = 18
REASSIGN_MIN_MINUTES = 15
REASSIGN_MAX_MINUTES = 30
WORKER_SEED_OFFSET = 7919  # arbitrary prime; keeps this RNG stream independent of sensor/permit generation


def worker_id(index: int) -> str:
    """1-indexed worker id, e.g. W01 .. W18."""
    return f"W{index:02d}"


def build_worker_registry(n_workers: int = N_WORKERS) -> pd.DataFrame:
    """Static worker table — just identity, no home zone (that's simulated)."""
    return pd.DataFrame({"worker_id": [worker_id(i) for i in range(1, n_workers + 1)]})


def _zone_restricted_matrix(
    risk_df: pd.DataFrame, zone_layout_df: pd.DataFrame, timestamps: list[pd.Timestamp]
) -> dict[str, np.ndarray]:
    """zone_id -> bool array (aligned to `timestamps`) of whether that zone
    is RESTRICTED at each step. Only oven_battery zones can be RESTRICTED —
    Coal Chemical Plant / Exhauster House have no ovens, so no gas hazard
    reading ever puts them over threshold here."""
    zone_of = oven_to_zone_map()
    df = risk_df[["oven_id", "timestamp", "risk_category"]].copy()
    df["zone_id"] = df["oven_id"].map(zone_of)
    df["is_high"] = df["risk_category"] == RiskCategory.HIGH.value

    pivot = df.pivot_table(index="timestamp", columns="zone_id", values="is_high", aggfunc="max", fill_value=False)
    pivot = pivot.reindex(timestamps).fillna(False).astype(bool)

    matrix = {zid: pivot[zid].to_numpy(dtype=bool) for zid in pivot.columns}

    non_oven_zones = zone_layout_df.loc[zone_layout_df["zone_type"] != ZoneType.OVEN_BATTERY.value, "zone_id"]
    for zid in non_oven_zones:
        matrix[zid] = np.zeros(len(timestamps), dtype=bool)
    return matrix


def _zone_status_df(matrix: dict[str, np.ndarray], timestamps: list[pd.Timestamp]) -> pd.DataFrame:
    rows = [
        {
            "zone_id": zid,
            "timestamp": ts,
            "status": ZoneStatus.RESTRICTED.value if restricted else ZoneStatus.NORMAL.value,
        }
        for zid, arr in matrix.items()
        for ts, restricted in zip(timestamps, arr)
    ]
    return pd.DataFrame(rows).sort_values(["zone_id", "timestamp"]).reset_index(drop=True)


def _event(seq: int, ts: pd.Timestamp, wid: str, zid: str, event_type: WorkerEventType) -> dict:
    if event_type is WorkerEventType.WARNING_ISSUED:
        message = f"Zone {zid} restricted — worker {wid} warned, entry blocked"
    else:
        message = f"Zone {zid} restricted — worker {wid} entry blocked, reassignment denied"
    return {
        "event_id": f"EVT{seq:04d}",
        "timestamp": ts,
        "worker_id": wid,
        "zone_id": zid,
        "event_type": event_type.value,
        "message": message,
    }


def _simulate_occupancy(
    zone_restricted: dict[str, np.ndarray],
    zone_ids: list[str],
    timestamps: list[pd.Timestamp],
    n_workers: int,
    interval_min: int,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed + WORKER_SEED_OFFSET)
    n_steps = len(timestamps)
    workers = [worker_id(i) for i in range(1, n_workers + 1)]

    def _gap_steps() -> int:
        minutes = int(rng.integers(REASSIGN_MIN_MINUTES, REASSIGN_MAX_MINUTES + 1))
        return max(1, minutes // interval_min)

    current_zone = {w: zone_ids[int(rng.integers(0, len(zone_ids)))] for w in workers}
    next_reassign_step = {w: _gap_steps() for w in workers}
    occupancy = {w: [""] * n_steps for w in workers}

    was_restricted = {zid: False for zid in zone_ids}
    events: list[dict] = []
    seq = 1

    for step in range(n_steps):
        ts = timestamps[step]

        # Periodic reassignment (every ~15-30 simulated minutes per worker) —
        # never continuous. A candidate zone that's currently RESTRICTED is
        # rejected outright: the worker stays at their prior zone instead of
        # silently moving in, and the rejection itself becomes an event. A
        # candidate that happens to equal the worker's current zone isn't an
        # entry attempt at all (nothing would change), so it's a no-op
        # regardless of that zone's status — avoids a spurious entry_blocked
        # event firing alongside a warning_issued for the same worker/zone.
        for w in workers:
            if step > 0 and step == next_reassign_step[w]:
                candidate = zone_ids[int(rng.integers(0, len(zone_ids)))]
                if candidate != current_zone[w]:
                    if zone_restricted[candidate][step]:
                        events.append(_event(seq, ts, w, candidate, WorkerEventType.ENTRY_BLOCKED))
                        seq += 1
                    else:
                        current_zone[w] = candidate
                next_reassign_step[w] = step + _gap_steps()
            occupancy[w][step] = current_zone[w]

        # Zone RESTRICTED transitions (rising edge only) warn whoever is
        # already standing in the zone at that exact moment.
        for zid in zone_ids:
            restricted_now = bool(zone_restricted[zid][step])
            if restricted_now and not was_restricted[zid]:
                for w in workers:
                    if occupancy[w][step] == zid:
                        events.append(_event(seq, ts, w, zid, WorkerEventType.WARNING_ISSUED))
                        seq += 1
            was_restricted[zid] = restricted_now

    occupancy_df = pd.concat(
        [pd.DataFrame({"worker_id": w, "timestamp": timestamps, "zone_id": occupancy[w]}) for w in workers],
        ignore_index=True,
    )
    events_df = pd.DataFrame(events, columns=["event_id", "timestamp", "worker_id", "zone_id", "event_type", "message"])
    return occupancy_df, events_df


def simulate(
    risk_df: pd.DataFrame,
    zone_layout_df: pd.DataFrame,
    n_workers: int = N_WORKERS,
    seed: int = C.RANDOM_SEED,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Returns (worker_registry_df, occupancy_df, events_df, zone_status_df)."""
    timestamps = sorted(risk_df["timestamp"].unique())
    matrix = _zone_restricted_matrix(risk_df, zone_layout_df, timestamps)
    zone_status_df = _zone_status_df(matrix, timestamps)

    zone_ids = zone_layout_df["zone_id"].tolist()
    occupancy_df, events_df = _simulate_occupancy(
        matrix, zone_ids, timestamps, n_workers, C.SAMPLE_INTERVAL_MIN, seed
    )
    worker_df = build_worker_registry(n_workers)
    return worker_df, occupancy_df, events_df, zone_status_df
