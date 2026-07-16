"""Regression tests for the ml_engine guard clauses added after code review:
a bad train_frac must fail loudly and specifically, not crash deep inside
sklearn or silently mislabel a straddled window.
"""

from __future__ import annotations

import pytest

from compoundrisk import ml_engine, rule_engine, simulate


@pytest.fixture(scope="module")
def generated():
    sensor_df, permit_df, ground_truth_df = simulate.generate()
    risk_df = rule_engine.run(sensor_df, permit_df)
    return sensor_df, permit_df, ground_truth_df, risk_df


def test_default_train_frac_runs_cleanly(generated):
    sensor_df, _, ground_truth_df, risk_df = generated
    output_df, metrics = ml_engine.train_and_score(sensor_df, risk_df, ground_truth_df)
    assert metrics["train_positive_rows"] > 0
    assert metrics["test_positive_rows"] > 0
    assert len(output_df) == len(sensor_df)


def test_train_frac_that_bisects_a_window_raises(generated):
    sensor_df, _, ground_truth_df, risk_df = generated
    # C06 spans hours 43-44 (scenarios.py); 43.5/60 lands the split inside it.
    with pytest.raises(ValueError, match="falls inside window"):
        ml_engine.train_and_score(sensor_df, risk_df, ground_truth_df, train_frac=43.5 / 60)


def test_train_frac_with_zero_positive_windows_before_split_raises(generated):
    sensor_df, _, ground_truth_df, risk_df = generated
    # First window (W01) starts at hour 6; a 3-hour train window has no positives.
    with pytest.raises(ValueError, match="single class"):
        ml_engine.train_and_score(sensor_df, risk_df, ground_truth_df, train_frac=3 / 60)


def test_build_feature_frame_raises_on_duplicate_risk_rows(generated):
    sensor_df, _, _, risk_df = generated
    duplicated_risk_df = risk_df.iloc[[0, 0] + list(range(1, len(risk_df)))].reset_index(drop=True)
    with pytest.raises(ValueError, match="merge changed row count"):
        ml_engine.build_feature_frame(sensor_df, duplicated_risk_df)
