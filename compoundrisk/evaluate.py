"""Phase 3 — evaluation.

Grades the rule engine's compound_risk_flag against the ground truth
recorded in compoundrisk/scenarios.py: it must catch every "compound"
(positive) window and stay quiet through every "confounder" (negative)
window as well as the ~53 ovens that never leave baseline operation.
"""

from __future__ import annotations

import pandas as pd

from compoundrisk import constants as C


def _window_mask(risk_df: pd.DataFrame, window: pd.Series) -> pd.Series:
    return (
        (risk_df["oven_id"] == window["oven_id"])
        & (risk_df["timestamp"] >= window["start_time"])
        & (risk_df["timestamp"] < window["end_time"])
    )


def label_ground_truth(risk_df: pd.DataFrame, ground_truth_df: pd.DataFrame) -> pd.Series:
    """True for any row (oven_id, timestamp) inside a should_flag=True window.

    Public because compoundrisk.ml_engine reuses this same ground-truth
    labeling to train/evaluate the optional ML layer against the identical
    definition of "positive" that the rule engine is graded against.
    """
    labels = pd.Series(False, index=risk_df.index)
    for _, window in ground_truth_df[ground_truth_df["should_flag"]].iterrows():
        labels |= _window_mask(risk_df, window)
    return labels


def evaluate(
    risk_df: pd.DataFrame, ground_truth_df: pd.DataFrame, flag_column: str = "compound_risk_flag"
) -> tuple[dict, pd.DataFrame]:
    gt_positive = label_ground_truth(risk_df, ground_truth_df)
    predicted = risk_df[flag_column].astype(bool)

    tp = int((gt_positive & predicted).sum())
    fp = int((~gt_positive & predicted).sum())
    fn = int((gt_positive & ~predicted).sum())
    tn = int((~gt_positive & ~predicted).sum())

    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else float("nan")

    per_window_rows = []
    confounder_mask = pd.Series(False, index=risk_df.index)
    for _, window in ground_truth_df.iterrows():
        mask = _window_mask(risk_df, window)
        window_rows = risk_df[mask]
        flagged_any = bool(window_rows[flag_column].any())
        flag_rate = float(window_rows[flag_column].mean()) if len(window_rows) else float("nan")
        correct = flagged_any if window["should_flag"] else (not flagged_any)
        per_window_rows.append(
            {
                "window_id": window["window_id"],
                "oven_id": window["oven_id"],
                "kind": window["kind"],
                "should_flag": bool(window["should_flag"]),
                "detected": flagged_any,
                "in_window_flag_rate": flag_rate,
                "correct": correct,
                "description": window["description"],
            }
        )
        if not window["should_flag"]:
            confounder_mask |= mask
    per_window_df = pd.DataFrame(per_window_rows)

    fp_in_confounder = int((confounder_mask & ~gt_positive & predicted).sum())
    fp_in_baseline = fp - fp_in_confounder

    positives = per_window_df[per_window_df["should_flag"]]
    confounders = per_window_df[~per_window_df["should_flag"]]

    summary = {
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "true_negatives": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "fp_in_confounder_windows": fp_in_confounder,
        "fp_in_baseline": fp_in_baseline,
        "windows_total_positive": len(positives),
        "windows_detected": int(positives["detected"].sum()),
        "windows_recall": float(positives["detected"].mean()) if len(positives) else float("nan"),
        "confounders_total": len(confounders),
        "confounders_correctly_quiet": int((~confounders["detected"]).sum()),
        "confounders_quiet_rate": float((~confounders["detected"]).mean()) if len(confounders) else float("nan"),
        "all_windows_correct": bool(per_window_df["correct"].all()),
    }
    return summary, per_window_df


def format_report(summary: dict, per_window_df: pd.DataFrame) -> str:
    lines = []
    lines.append("=" * 72)
    lines.append("PHASE 3 EVALUATION — Compound Risk Detection Engine (rule-based)")
    lines.append("=" * 72)
    lines.append("")
    lines.append(
        f"Injected compound-risk windows caught: {summary['windows_detected']}/"
        f"{summary['windows_total_positive']} (recall = {summary['windows_recall']:.0%})"
    )
    lines.append(
        f"Confounder windows correctly left quiet: {summary['confounders_correctly_quiet']}/"
        f"{summary['confounders_total']} (quiet rate = {summary['confounders_quiet_rate']:.0%})"
    )
    lines.append("")
    lines.append("Per-timestamp confusion matrix (every oven x every 5-min sample):")
    lines.append(f"  TP={summary['true_positives']}  FP={summary['false_positives']}  "
                 f"FN={summary['false_negatives']}  TN={summary['true_negatives']}")
    lines.append(f"  precision={summary['precision']:.3f}  recall={summary['recall']:.3f}  f1={summary['f1']:.3f}")
    if summary["false_positives"]:
        lines.append(
            f"  false positives: {summary['fp_in_confounder_windows']} inside confounder windows, "
            f"{summary['fp_in_baseline']} during pure baseline"
        )
    lines.append("")
    lines.append(f"CO alert threshold: {C.CO_ALERT_PPM:.0f} ppm | LEL alert threshold: {C.LEL_CONFINED_ENTRY_PCT:.0f}%")
    lines.append("")
    lines.append("Per-window detail:")
    for _, row in per_window_df.iterrows():
        mark = "PASS" if row["correct"] else "FAIL"
        expect = "should flag" if row["should_flag"] else "should stay quiet"
        got = "flagged" if row["detected"] else "quiet"
        lines.append(
            f"  [{mark}] {row['window_id']} ({row['oven_id']}, {row['kind']}) — {expect}, engine {got}"
            f" | in-window flag rate: {row['in_window_flag_rate']:.0%}"
        )
        lines.append(f"         {row['description']}")
    lines.append("")
    overall = "ALL WINDOWS CORRECT" if summary["all_windows_correct"] else "SOME WINDOWS INCORRECT — see FAIL above"
    lines.append(f"Result: {overall}")
    lines.append("=" * 72)
    return "\n".join(lines)
