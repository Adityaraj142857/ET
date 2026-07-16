"""Orchestrates Phases 1-3: generate -> detect -> evaluate.

Saves every table from Section 4 to data/ as CSV and prints the Phase 3
evaluation report (plus the optional ML stretch comparison) to stdout.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from compoundrisk import constants as C
from compoundrisk import evaluate, export_frontend, ml_engine, rule_engine, simulate, workers
from compoundrisk.registry import build_oven_registry, build_zone_layout

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = REPO_ROOT / "data"
DEFAULT_FRONTEND_DATA_PATH = REPO_ROOT / "frontend" / "public" / "data" / "scene.json"


def run_pipeline(
    data_dir: Path = DEFAULT_DATA_DIR,
    run_ml_stretch: bool = True,
    frontend_data_path: Path | None = DEFAULT_FRONTEND_DATA_PATH,
) -> dict:
    data_dir.mkdir(parents=True, exist_ok=True)

    oven_registry_df = build_oven_registry()
    zone_layout_df = build_zone_layout()
    sensor_df, permit_df, ground_truth_df = simulate.generate()
    risk_df = rule_engine.run(sensor_df, permit_df)
    summary, per_window_df = evaluate.evaluate(risk_df, ground_truth_df)
    worker_df, occupancy_df, worker_events_df, zone_status_df = workers.simulate(risk_df, zone_layout_df)

    oven_registry_df.to_csv(data_dir / "oven_registry.csv", index=False)
    zone_layout_df.to_csv(data_dir / "zone_layout.csv", index=False)
    sensor_df.to_csv(data_dir / "sensor_readings.csv", index=False)
    permit_df.to_csv(data_dir / "permit_log.csv", index=False)
    ground_truth_df.to_csv(data_dir / "ground_truth_windows.csv", index=False)
    risk_df.to_csv(data_dir / "risk_engine_output.csv", index=False)
    per_window_df.to_csv(data_dir / "evaluation_per_window.csv", index=False)
    worker_df.to_csv(data_dir / "worker_registry.csv", index=False)
    zone_status_df.to_csv(data_dir / "zone_status.csv", index=False)
    occupancy_df.to_csv(data_dir / "worker_occupancy.csv", index=False)
    worker_events_df.to_csv(data_dir / "worker_events.csv", index=False)

    print(f"Generated {len(sensor_df):,} sensor readings across {C.N_OVENS} ovens "
          f"over a {C.SIM_HOURS}h window ({len(permit_df)} permits, "
          f"{len(ground_truth_df)} labeled ground-truth windows).")
    print(f"Simulated {len(worker_df)} workers with zone-level occupancy "
          f"({len(worker_events_df)} access-restriction events).")
    print()
    report = evaluate.format_report(summary, per_window_df)
    print(report)

    ml_metrics = None
    if run_ml_stretch:
        ml_output_df, ml_metrics = ml_engine.train_and_score(sensor_df, risk_df, ground_truth_df)
        ml_output_df.to_csv(data_dir / "ml_enhanced_risk_output.csv", index=False)
        print()
        print(ml_engine.format_report(ml_metrics))

    with open(data_dir / "evaluation_report.txt", "w") as f:
        f.write(report)
        if ml_metrics is not None:
            f.write("\n\n")
            f.write(ml_engine.format_report(ml_metrics))

    if frontend_data_path is not None:
        payload = export_frontend.build_payload(
            sensor_df, permit_df, risk_df, worker_df, occupancy_df, worker_events_df, zone_status_df
        )
        export_frontend.write_payload(payload, frontend_data_path)
        size_mb = frontend_data_path.stat().st_size / 1_000_000
        print(f"\nWrote frontend scene data to {frontend_data_path} ({size_mb:.1f} MB).")

    return {
        "summary": summary,
        "per_window_df": per_window_df,
        "ml_metrics": ml_metrics,
    }
