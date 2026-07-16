"""Boundary-condition tests for the Section 3 compound risk rule.

Each test isolates exactly one boundary so a regression points straight at
the broken condition instead of a vague "engine behaves differently."
"""

from __future__ import annotations

import pandas as pd
import pytest

from compoundrisk import constants as C
from compoundrisk import rule_engine

T0 = pd.Timestamp("2026-01-01 00:00:00")
OVEN = "TEST-O1"


def _sensor_row(co_ppm=8.0, lel=0.8, exhauster="normal", maintenance=False, timestamp=T0, oven_id=OVEN):
    return {
        "timestamp": timestamp,
        "oven_id": oven_id,
        "gas_temp_c": 400.0,
        "co_ppm": co_ppm,
        "combustible_gas_pct_lel": lel,
        "exhauster_status": exhauster,
        "maintenance_flag": maintenance,
    }


def _permit_row(permit_type="hot_work", status="active", oven_id=OVEN, issued=T0 - pd.Timedelta(minutes=10),
                 valid_until=T0 + pd.Timedelta(minutes=10), permit_id="P0001"):
    return {
        "permit_id": permit_id,
        "oven_id": oven_id,
        "permit_type": permit_type,
        "status": status,
        "issued_time": issued,
        "valid_until": valid_until,
    }


def _run(sensor_rows, permit_rows):
    sensor_df = pd.DataFrame(sensor_rows)
    permit_df = pd.DataFrame(permit_rows) if permit_rows else pd.DataFrame(
        columns=["permit_id", "oven_id", "permit_type", "status", "issued_time", "valid_until"]
    )
    return rule_engine.run(sensor_df, permit_df)


class TestGasThreshold:
    def test_co_exactly_at_threshold_does_not_trigger(self):
        result = _run([_sensor_row(co_ppm=C.CO_ALERT_PPM, maintenance=True)], [_permit_row()])
        assert not result.iloc[0]["gas_condition"]
        assert not result.iloc[0]["compound_risk_flag"]

    def test_co_just_above_threshold_triggers(self):
        result = _run([_sensor_row(co_ppm=C.CO_ALERT_PPM + 0.01, maintenance=True)], [_permit_row()])
        assert result.iloc[0]["gas_condition"]
        assert result.iloc[0]["compound_risk_flag"]

    def test_lel_exactly_at_threshold_does_not_trigger(self):
        result = _run(
            [_sensor_row(co_ppm=1.0, lel=C.LEL_CONFINED_ENTRY_PCT, maintenance=True)], [_permit_row()]
        )
        assert not result.iloc[0]["gas_condition"]
        assert not result.iloc[0]["compound_risk_flag"]

    def test_lel_just_above_threshold_triggers(self):
        result = _run(
            [_sensor_row(co_ppm=1.0, lel=C.LEL_CONFINED_ENTRY_PCT + 0.01, maintenance=True)], [_permit_row()]
        )
        assert result.iloc[0]["gas_condition"]
        assert result.iloc[0]["compound_risk_flag"]


class TestPermitCondition:
    def test_closed_permit_does_not_count_even_within_time_bounds(self):
        result = _run(
            [_sensor_row(co_ppm=100.0, maintenance=True)],
            [_permit_row(status="closed")],
        )
        assert not result.iloc[0]["permit_active"]
        assert not result.iloc[0]["compound_risk_flag"]

    def test_cold_work_permit_does_not_satisfy_permit_condition(self):
        result = _run(
            [_sensor_row(co_ppm=100.0, maintenance=True)],
            [_permit_row(permit_type="cold_work")],
        )
        assert not result.iloc[0]["permit_active"]
        assert not result.iloc[0]["compound_risk_flag"]

    def test_confined_space_entry_permit_counts(self):
        result = _run(
            [_sensor_row(co_ppm=100.0, maintenance=True)],
            [_permit_row(permit_type="confined_space_entry")],
        )
        assert result.iloc[0]["permit_active"]
        assert result.iloc[0]["compound_risk_flag"]

    def test_permit_outside_time_bounds_does_not_count(self):
        result = _run(
            [_sensor_row(co_ppm=100.0, maintenance=True)],
            [_permit_row(issued=T0 - pd.Timedelta(hours=2), valid_until=T0 - pd.Timedelta(hours=1))],
        )
        assert not result.iloc[0]["permit_active"]
        assert not result.iloc[0]["compound_risk_flag"]

    def test_no_permit_at_all_does_not_flag(self):
        result = _run([_sensor_row(co_ppm=100.0, maintenance=True)], [])
        assert not result.iloc[0]["permit_active"]
        assert not result.iloc[0]["compound_risk_flag"]


class TestMaintenanceOrExhausterCondition:
    def test_maintenance_flag_alone_satisfies_third_factor(self):
        result = _run(
            [_sensor_row(co_ppm=100.0, exhauster="normal", maintenance=True)], [_permit_row()]
        )
        assert result.iloc[0]["maintenance_condition"]
        assert result.iloc[0]["compound_risk_flag"]

    def test_exhauster_fault_alone_satisfies_third_factor(self):
        result = _run(
            [_sensor_row(co_ppm=100.0, exhauster="fault", maintenance=False)], [_permit_row()]
        )
        assert result.iloc[0]["maintenance_condition"]
        assert result.iloc[0]["compound_risk_flag"]

    def test_neither_maintenance_nor_fault_blocks_flag(self):
        result = _run(
            [_sensor_row(co_ppm=100.0, exhauster="normal", maintenance=False)], [_permit_row()]
        )
        assert not result.iloc[0]["maintenance_condition"]
        assert not result.iloc[0]["compound_risk_flag"]


class TestTwoOfThreeIsNotEnough:
    """The whole point of a compound-risk engine: no single pair of factors should trigger it."""

    def test_gas_and_permit_without_maintenance_or_fault(self):
        result = _run([_sensor_row(co_ppm=100.0, maintenance=False, exhauster="normal")], [_permit_row()])
        assert not result.iloc[0]["compound_risk_flag"]

    def test_gas_and_maintenance_without_permit(self):
        result = _run([_sensor_row(co_ppm=100.0, maintenance=True)], [])
        assert not result.iloc[0]["compound_risk_flag"]

    def test_permit_and_maintenance_without_gas(self):
        result = _run([_sensor_row(co_ppm=5.0, lel=0.5, maintenance=True)], [_permit_row()])
        assert not result.iloc[0]["compound_risk_flag"]


class TestRiskReasonAndScore:
    def test_normal_row_has_generic_reason_and_zero_score(self):
        result = _run([_sensor_row()], [])
        row = result.iloc[0]
        assert row["risk_reason"] == "Normal operating parameters"
        assert row["risk_score"] == 0.0
        assert row["risk_category"] == "low"

    def test_flagged_row_reason_mentions_all_three_factors(self):
        result = _run([_sensor_row(co_ppm=78.0, maintenance=True)], [_permit_row(permit_type="hot_work")])
        reason = result.iloc[0]["risk_reason"]
        assert "CO 78ppm" in reason
        assert "hot-work permit" in reason
        assert "maintenance flag" in reason

    def test_compound_flag_always_scores_high_category_even_barely_over_threshold(self):
        result = _run([_sensor_row(co_ppm=50.01, maintenance=True)], [_permit_row()])
        assert result.iloc[0]["compound_risk_flag"]
        assert result.iloc[0]["risk_category"] == "high"

    def test_score_is_monotonic_in_gas_severity(self):
        low = _run([_sensor_row(co_ppm=60.0, maintenance=True)], [_permit_row()]).iloc[0]["risk_score"]
        high = _run([_sensor_row(co_ppm=150.0, maintenance=True)], [_permit_row()]).iloc[0]["risk_score"]
        assert high >= low

    def test_two_of_three_never_categorizes_as_high_even_at_max_gas_severity(self):
        """Regression: a weighted-sum score cutoff previously let a maxed-out
        gas reading + permit (no maintenance/fault) reach "high" — exactly
        the two-of-three pattern the engine exists to reject."""
        result = _run([_sensor_row(co_ppm=500.0, maintenance=False, exhauster="normal")], [_permit_row()])
        assert not result.iloc[0]["compound_risk_flag"]
        assert result.iloc[0]["risk_category"] != "high"
        assert result.iloc[0]["risk_category"] == "medium"

    def test_single_factor_present_is_medium_not_low(self):
        result = _run([_sensor_row(co_ppm=55.0, maintenance=False, exhauster="normal")], [])
        assert result.iloc[0]["risk_category"] == "medium"

    def test_no_factors_present_is_low(self):
        result = _run([_sensor_row()], [])
        assert result.iloc[0]["risk_category"] == "low"


class TestPermitTypeDeterminism:
    def test_most_recently_issued_qualifying_permit_wins(self):
        older = _permit_row(
            permit_type="confined_space_entry", permit_id="P0001",
            issued=T0 - pd.Timedelta(minutes=30), valid_until=T0 + pd.Timedelta(minutes=30),
        )
        newer = _permit_row(
            permit_type="hot_work", permit_id="P0002",
            issued=T0 - pd.Timedelta(minutes=5), valid_until=T0 + pd.Timedelta(minutes=30),
        )
        result = _run([_sensor_row(co_ppm=100.0, maintenance=True)], [older, newer])
        assert result.iloc[0]["permit_active"]
        assert result.iloc[0]["compound_risk_flag"]
        assert "hot-work permit" in result.iloc[0]["risk_reason"]
