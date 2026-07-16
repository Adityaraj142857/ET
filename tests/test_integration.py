"""End-to-end regression test for Phases 1-3: generate -> detect -> evaluate.

This is the test that actually matters for the hackathon claim in Section 5
Phase 3: "confirm the engine catches all injected risk windows and stays
quiet during normal periods." Everything else is a supporting boundary
check; this is the one that would catch a scenario/engine drifting apart.
"""

from __future__ import annotations

from compoundrisk import constants as C
from compoundrisk import evaluate, rule_engine, simulate
from compoundrisk.schemas import ExhausterStatus, PermitType


def _generate_once():
    sensor_df, permit_df, ground_truth_df = simulate.generate()
    risk_df = rule_engine.run(sensor_df, permit_df)
    return sensor_df, permit_df, ground_truth_df, risk_df


def test_engine_catches_every_positive_window_and_stays_quiet_on_confounders():
    _, _, ground_truth_df, risk_df = _generate_once()
    summary, per_window_df = evaluate.evaluate(risk_df, ground_truth_df)

    assert summary["windows_recall"] == 1.0, per_window_df[per_window_df["should_flag"]]
    assert summary["confounders_quiet_rate"] == 1.0, per_window_df[~per_window_df["should_flag"]]
    assert summary["false_positives"] == 0
    assert summary["all_windows_correct"]


def test_generation_is_deterministic_given_the_same_seed():
    sensor_a, _, _, risk_a = _generate_once()
    sensor_b, _, _, risk_b = _generate_once()
    pd_assert_frame_equal(sensor_a, sensor_b)
    pd_assert_frame_equal(risk_a, risk_b)


def pd_assert_frame_equal(a, b):
    import pandas.testing as pdt

    pdt.assert_frame_equal(a, b)


def test_baseline_gas_readings_never_cross_threshold_outside_labeled_windows():
    """The false-positive guarantee depends on this: baseline CO/LEL are hard
    -clipped below the alert thresholds, so gas_condition can only ever be
    True inside a deliberately injected scenarios.WINDOWS spike. Confounder
    windows C01/C04/C05/C06 legitimately exceed threshold by design, so
    they're excluded from "baseline" here rather than counted as violations.
    """
    sensor_df, _, ground_truth_df, _ = _generate_once()

    any_window_mask = None
    for _, window in ground_truth_df.iterrows():
        mask = evaluate._window_mask(sensor_df, window)
        any_window_mask = mask if any_window_mask is None else (any_window_mask | mask)

    outside = sensor_df[~any_window_mask]
    assert (outside["co_ppm"] <= C.CO_ALERT_PPM).all()
    assert (outside["combustible_gas_pct_lel"] <= C.LEL_CONFINED_ENTRY_PCT).all()


def test_gas_temp_stays_within_the_real_cooling_curve_band():
    sensor_df, _, _, _ = _generate_once()
    assert sensor_df["gas_temp_c"].min() > 40.0
    assert sensor_df["gas_temp_c"].max() < 860.0


def test_sensor_and_permit_enums_are_valid():
    sensor_df, permit_df, _, _ = _generate_once()
    assert set(sensor_df["exhauster_status"].unique()) <= {e.value for e in ExhausterStatus}
    assert set(permit_df["permit_type"].unique()) <= {e.value for e in PermitType}
    assert sensor_df["maintenance_flag"].dtype == bool


def test_permit_log_never_has_issued_after_valid_until():
    _, permit_df, _, _ = _generate_once()
    assert (permit_df["issued_time"] <= permit_df["valid_until"]).all()
