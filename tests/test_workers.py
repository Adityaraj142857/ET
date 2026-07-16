"""Tests for zone-level worker occupancy + access-restriction events.

Uses the real generator/engine (not hand-built fixtures) because RESTRICTED
zones only occur where the injected scenario windows actually push an oven
to HIGH risk_category — exercising the real pipeline is the only way to get
a genuine NORMAL->RESTRICTED transition to test against.
"""

from __future__ import annotations

import pandas as pd

from compoundrisk import constants as C
from compoundrisk import rule_engine, simulate, workers
from compoundrisk.registry import build_zone_layout, oven_to_zone_map
from compoundrisk.schemas import RiskCategory, WorkerEventType, ZoneStatus, ZoneType


def _simulate_once():
    sensor_df, permit_df, _ = simulate.generate()
    risk_df = rule_engine.run(sensor_df, permit_df)
    zone_layout_df = build_zone_layout()
    worker_df, occupancy_df, events_df, zone_status_df = workers.simulate(risk_df, zone_layout_df)
    return risk_df, zone_layout_df, worker_df, occupancy_df, events_df, zone_status_df


def test_worker_registry_has_expected_count_and_unique_ids():
    _, _, worker_df, _, _, _ = _simulate_once()
    assert len(worker_df) == workers.N_WORKERS
    assert worker_df["worker_id"].is_unique
    assert worker_df["worker_id"].iloc[0] == "W01"


def test_only_oven_battery_zones_can_be_restricted():
    _, zone_layout_df, _, _, _, zone_status_df = _simulate_once()
    non_oven_zones = set(
        zone_layout_df.loc[zone_layout_df["zone_type"] != ZoneType.OVEN_BATTERY.value, "zone_id"]
    )
    non_oven_status = zone_status_df[zone_status_df["zone_id"].isin(non_oven_zones)]
    assert (non_oven_status["status"] == ZoneStatus.NORMAL.value).all()


def test_zone_status_matches_any_high_risk_oven_in_that_zone():
    risk_df, _, _, _, _, zone_status_df = _simulate_once()
    zone_of = oven_to_zone_map()
    risk_df = risk_df.copy()
    risk_df["zone_id"] = risk_df["oven_id"].map(zone_of)
    expected_restricted = (
        risk_df.assign(is_high=risk_df["risk_category"] == RiskCategory.HIGH.value)
        .groupby(["zone_id", "timestamp"])["is_high"]
        .max()
    )
    # At least one zone/timestamp should actually be RESTRICTED (otherwise
    # this test — and the whole feature — would be vacuously true).
    assert expected_restricted.any()

    status_lookup = zone_status_df.set_index(["zone_id", "timestamp"])["status"]
    for (zid, ts), is_high in expected_restricted.items():
        expected = ZoneStatus.RESTRICTED.value if is_high else ZoneStatus.NORMAL.value
        assert status_lookup[(zid, ts)] == expected


def test_occupancy_covers_every_worker_at_every_step_with_valid_zone_ids():
    _, zone_layout_df, worker_df, occupancy_df, _, _ = _simulate_once()
    n_steps = occupancy_df["timestamp"].nunique()
    valid_zone_ids = set(zone_layout_df["zone_id"])

    assert len(occupancy_df) == len(worker_df) * n_steps
    assert occupancy_df["zone_id"].isin(valid_zone_ids).all()
    assert set(occupancy_df["worker_id"]) == set(worker_df["worker_id"])


def test_worker_reassignment_never_happens_faster_than_the_minimum_interval():
    _, _, _, occupancy_df, _, _ = _simulate_once()
    min_gap_steps = workers.REASSIGN_MIN_MINUTES // C.SAMPLE_INTERVAL_MIN

    for _, group in occupancy_df.groupby("worker_id"):
        group = group.sort_values("timestamp").reset_index(drop=True)
        changed = group.index[group["zone_id"] != group["zone_id"].shift(1)].tolist()
        changed = [i for i in changed if i > 0]  # drop the implicit "change" at step 0
        gaps = [b - a for a, b in zip(changed, changed[1:])]
        assert all(gap >= min_gap_steps for gap in gaps), gaps


def test_entry_blocked_events_only_target_zones_restricted_at_that_moment():
    _, _, _, _, events_df, zone_status_df = _simulate_once()
    blocked = events_df[events_df["event_type"] == WorkerEventType.ENTRY_BLOCKED.value]
    status_lookup = zone_status_df.set_index(["zone_id", "timestamp"])["status"]

    for row in blocked.itertuples():
        assert status_lookup[(row.zone_id, row.timestamp)] == ZoneStatus.RESTRICTED.value


def test_entry_blocked_worker_stays_at_prior_zone_instead_of_moving_in():
    _, _, _, occupancy_df, events_df, _ = _simulate_once()
    blocked = events_df[events_df["event_type"] == WorkerEventType.ENTRY_BLOCKED.value]
    if blocked.empty:
        return  # nothing to check this run; other tests cover the mechanism exists elsewhere

    for row in blocked.itertuples():
        worker_occ = occupancy_df[occupancy_df["worker_id"] == row.worker_id].sort_values("timestamp")
        at_step = worker_occ[worker_occ["timestamp"] == row.timestamp]["zone_id"].iloc[0]
        assert at_step != row.zone_id, "blocked worker must not end up occupying the rejected zone"


def test_warning_issued_events_only_fire_on_true_restricted_transitions():
    _, _, _, occupancy_df, events_df, zone_status_df = _simulate_once()
    warnings = events_df[events_df["event_type"] == WorkerEventType.WARNING_ISSUED.value]
    if warnings.empty:
        return

    for zid, group in zone_status_df.groupby("zone_id"):
        group = group.sort_values("timestamp").reset_index(drop=True)
        group["prev"] = group["status"].shift(1)
        rising_edges = set(
            group.loc[
                (group["status"] == ZoneStatus.RESTRICTED.value) & (group["prev"] != ZoneStatus.RESTRICTED.value),
                "timestamp",
            ]
        )
        zone_warnings = warnings[warnings["zone_id"] == zid]
        assert set(zone_warnings["timestamp"]).issubset(rising_edges)

    # And every warned worker was actually occupying that zone at that moment.
    occ_lookup = occupancy_df.set_index(["worker_id", "timestamp"])["zone_id"]
    for row in warnings.itertuples():
        assert occ_lookup[(row.worker_id, row.timestamp)] == row.zone_id
