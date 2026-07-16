"""Optional Phase 2 stretch — gradient boosting layer producing a continuous ml_risk_score.

Framed as an ENHANCEMENT over the rule engine, not a replacement: the rule
engine's binary compound_risk_flag is still the explainable/defensible
signal that Phase 3 evaluation is scored against. This module exists to
show what a smoother, magnitude-aware score could add on top (e.g. for the
Phase-4 heatmap's color gradient), while staying honest about how little
labeled data a hackathon-scale synthetic run actually provides.

Why gradient boosting and not logistic regression (the spec names both as
options): the Section 3 rule is a three-way AND — gas AND permit AND
(maintenance OR exhauster fault). A linear model scores each feature
independently and sums them, so it cannot represent an AND-shaped decision
boundary from the raw 0/1 feature values without hand-built interaction
terms; two-of-three-present would score almost as high as three-of-three.
Tree ensembles split on thresholds and naturally capture that interaction,
which is the entire point of a "compound" risk engine.
"""

from __future__ import annotations

import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import precision_recall_fscore_support, roc_auc_score
from sklearn.utils.class_weight import compute_sample_weight

from compoundrisk import constants as C
from compoundrisk.evaluate import label_ground_truth
from compoundrisk.schemas import ExhausterStatus

FEATURE_COLUMNS = [
    "co_ppm",
    "combustible_gas_pct_lel",
    "gas_temp_c",
    "permit_active",
    "maintenance_flag",
    "exhauster_fault",
]


def build_feature_frame(sensor_df: pd.DataFrame, risk_df: pd.DataFrame) -> pd.DataFrame:
    """Raw per-factor features (not the rule engine's pre-OR'd conditions) —
    the model needs to learn the AND/OR interaction itself, not be handed it."""
    df = sensor_df.merge(
        risk_df[["oven_id", "timestamp", "permit_active"]], on=["oven_id", "timestamp"], how="left"
    )
    if len(df) != len(sensor_df):
        raise ValueError(
            "build_feature_frame: merge changed row count "
            f"({len(sensor_df)} -> {len(df)}) — risk_df must have exactly one row per "
            "(oven_id, timestamp) in sensor_df, otherwise labels desync from features."
        )
    df["exhauster_fault"] = (df["exhauster_status"] == ExhausterStatus.FAULT.value).astype(int)
    df["maintenance_flag"] = df["maintenance_flag"].astype(int)
    df["permit_active"] = df["permit_active"].astype(int)
    return df


def train_and_score(
    sensor_df: pd.DataFrame,
    risk_df: pd.DataFrame,
    ground_truth_df: pd.DataFrame,
    train_frac: float = 0.7,
    seed: int = C.RANDOM_SEED,
) -> tuple[pd.DataFrame, dict]:
    """Time-ordered train/test split (train = first `train_frac` of the
    simulated window) — a random row split would leak signal between
    adjacent 5-minute samples inside the same event into both sides."""
    features_df = build_feature_frame(sensor_df, risk_df)
    labels = label_ground_truth(features_df, ground_truth_df)

    split_time = C.SIM_START + pd.Timedelta(hours=C.SIM_HOURS * train_frac)
    straddling = ground_truth_df[
        (ground_truth_df["start_time"] < split_time) & (split_time < ground_truth_df["end_time"])
    ]
    if not straddling.empty:
        raise ValueError(
            f"train_frac={train_frac} puts the split at {split_time}, which falls inside "
            f"window(s) {list(straddling['window_id'])} — that would split one labeled event "
            "across train and test, exactly the leakage this time-ordered split exists to avoid. "
            "Pick a train_frac that lands between windows."
        )

    train_mask = features_df["timestamp"] < split_time
    test_mask = ~train_mask

    X = features_df[FEATURE_COLUMNS]
    X_train, y_train = X[train_mask], labels[train_mask]
    X_test, y_test = X[test_mask], labels[test_mask]

    if y_train.nunique() < 2:
        raise ValueError(
            f"train_frac={train_frac} leaves zero ground-truth-positive rows before {split_time} — "
            "a classifier can't be trained on a single class. Increase train_frac so at least one "
            "positive window falls before the split."
        )

    sample_weight = compute_sample_weight(class_weight="balanced", y=y_train)
    model = GradientBoostingClassifier(n_estimators=200, max_depth=3, learning_rate=0.1, random_state=seed)
    model.fit(X_train, y_train, sample_weight=sample_weight)

    ml_score_all = model.predict_proba(X)[:, 1]
    features_df["ml_risk_score"] = ml_score_all
    features_df["ml_predicted_flag"] = ml_score_all >= 0.5

    test_pred = features_df.loc[test_mask, "ml_predicted_flag"]
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_test, test_pred, average="binary", zero_division=0
    )
    metrics = {
        "train_rows": int(train_mask.sum()),
        "test_rows": int(test_mask.sum()),
        "train_positive_rows": int(y_train.sum()),
        "test_positive_rows": int(y_test.sum()),
        "test_precision": float(precision),
        "test_recall": float(recall),
        "test_f1": float(f1),
    }
    metrics["test_roc_auc"] = (
        float(roc_auc_score(y_test, ml_score_all[test_mask.values])) if y_test.nunique() > 1 else float("nan")
    )

    output = features_df[["oven_id", "timestamp", "ml_risk_score", "ml_predicted_flag"]].merge(
        risk_df[["oven_id", "timestamp", "risk_score", "compound_risk_flag"]], on=["oven_id", "timestamp"]
    )
    output = output.rename(columns={"risk_score": "rule_risk_score", "compound_risk_flag": "rule_compound_flag"})
    return output, metrics


def format_report(metrics: dict) -> str:
    lines = [
        "-" * 72,
        "OPTIONAL STRETCH — Gradient boosting ml_risk_score (enhancement, not a replacement)",
        "-" * 72,
        f"Train window: {metrics['train_rows']} rows ({metrics['train_positive_rows']} ground-truth positive)",
        f"Test window:  {metrics['test_rows']} rows ({metrics['test_positive_rows']} ground-truth positive)",
        f"Test precision={metrics['test_precision']:.3f}  recall={metrics['test_recall']:.3f}  "
        f"f1={metrics['test_f1']:.3f}  roc_auc={metrics['test_roc_auc']:.3f}",
    ]
    if metrics["test_positive_rows"] < 20:
        lines.append(
            "Caveat: very few positive examples fall in the held-out test window at hackathon "
            "data scale — treat these metrics as directional, not a certified model."
        )
    lines.append("-" * 72)
    return "\n".join(lines)
