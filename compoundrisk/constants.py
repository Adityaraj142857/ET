"""Fact-checked real-plant constants and alert thresholds.

Every numeric value here traces back to Section 2 ("Real Plant Data") and
Section 3 ("Core Risk Rule") of coke_oven_risk_project_context.md. Do not
change these without re-checking that document — the whole project's
credibility rests on these being the fact-checked figures, not placeholders.
"""

from __future__ import annotations

import pandas as pd

# --- Plant identity (RINL Vizag Steel, Battery 1 only — demo scope) ---
BATTERY_ID = "B1"
N_OVENS = 67
OVEN_VOLUME_M3 = 41.6
COAL_CHARGE_TONS = 32.0

# --- Process parameters ---
CARBONIZATION_TEMP_MIN_C = 1000.0
CARBONIZATION_TEMP_MAX_C = 1050.0
COKING_CYCLE_HOURS_MIN = 16.0
COKING_CYCLE_HOURS_MAX = 19.0

# Raw coke oven gas cooling curve: hottest right after charging (fresh coal
# devolatilization), cools toward ammonia-liquor-spray outlet temp as the
# charge cokes out and gas evolution tapers off through the cycle.
GAS_TEMP_CHARGE_C = 800.0
GAS_TEMP_FLOOR_C = 80.0

# --- Gas hazard thresholds (Section 2 — reference values, not statutory) ---
CO_ALERT_PPM = 50.0  # 8-hr PEL reference
LEL_NO_HOT_WORK_PCT = 0.0  # hot work requires zero LEL reading
LEL_CONFINED_ENTRY_PCT = 5.0  # confined space entry w/o BA up to this
LEL_MASK_ENTRY_PCT = 20.0  # entry with air-supplied mask up to this
MIN_O2_PCT = 19.0

# --- Simulation window ---
SIM_START = pd.Timestamp("2026-01-15 06:00:00")
SIM_HOURS = 60  # within the spec's 48-72hr band
SAMPLE_INTERVAL_MIN = 5
RANDOM_SEED = 42

# --- Zone grouping (~10 ovens per zone, feeds the future 3D heatmap) ---
OVENS_PER_ZONE = 10

# --- Compound risk rule weighting (Section 3) ---
# risk_score is a continuous 0-1 gradient for visualization; the binary
# compound-risk flag (what evaluation is scored against) requires ALL THREE
# factors regardless of score. Weights are additive components, not a
# probability model — this is a rule engine, not a classifier.
GAS_SCORE_WEIGHT = 0.5
PERMIT_SCORE_WEIGHT = 0.25
MAINTENANCE_SCORE_WEIGHT = 0.25

PERMIT_TYPES_THAT_COUNT = frozenset({"hot_work", "confined_space_entry"})
