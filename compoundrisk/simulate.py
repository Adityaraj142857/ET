"""Phase 1 — synthetic data generator.

Produces the Sensor Readings (4.2), Permit Log (4.3) tables plus a
ground_truth table (not part of the spec's four tables — an evaluation-only
artifact recording which windows *should* be flagged, so Phase 3 can grade
the engine objectively instead of eyeballing it).

Process modeling notes (why the numbers move the way they do):
- Each oven has its own staggered coking cycle (16-19h, randomized per
  cycle) so the battery pushes ovens in a round-robin sequence rather than
  all 67 charging in lockstep — that's how a real battery operates.
- gas_temp_c follows the real 800C -> 80C raw-gas cooling curve: hottest
  right after charging (fresh coal devolatilization drives peak gas
  evolution), decaying toward the ammonia-liquor-spray outlet temperature
  as the charge cokes out and gas evolution tapers off before the next
  charge.
- Baseline CO/LEL are hard-clipped below the Section-3 alert thresholds
  (35 ppm / 3.5% LEL ceilings vs. 50 ppm / 5% thresholds) so gas_condition
  can only ever be True inside a deliberately injected scenarios.WINDOWS
  spike. That is what makes the Phase-3 "stays quiet during normal
  operation" claim a guarantee rather than a hope: false positives outside
  the 6 confounder windows are structurally impossible, not just unlikely.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from compoundrisk import constants as C
from compoundrisk.registry import oven_id, oven_to_zone_map
from compoundrisk.scenarios import WINDOWS, RiskWindow
from compoundrisk.schemas import ExhausterStatus, PermitStatus

_LOG_20 = math.log(20.0)  # exp(-3.0) ~= 0.05 -> "decayed to 5% of the way from floor"


def _timestamps(sim_hours: int = C.SIM_HOURS, interval_min: int = C.SAMPLE_INTERVAL_MIN) -> pd.DatetimeIndex:
    n_steps = int(sim_hours * 60 // interval_min)
    return pd.date_range(C.SIM_START, periods=n_steps, freq=f"{interval_min}min")


def _t_hours(timestamps: pd.DatetimeIndex) -> np.ndarray:
    return ((timestamps - C.SIM_START) / pd.Timedelta(hours=1)).to_numpy()


def _charge_schedule(rng: np.random.Generator, oven_index: int, n_ovens: int, sim_hours: float) -> np.ndarray:
    """Sorted charge times (hours from sim start, may be negative) for one oven.

    Ovens are staggered round-robin across one mean cycle length so charges
    spread evenly through time, matching how a battery actually sequences
    pushes across its ovens instead of charging them all simultaneously.
    """
    mean_cycle = (C.COKING_CYCLE_HOURS_MIN + C.COKING_CYCLE_HOURS_MAX) / 2
    stagger_step = mean_cycle / n_ovens
    base_offset = (oven_index - 1) * stagger_step

    times = [base_offset]
    while times[-1] > -mean_cycle * 1.5:
        times.append(times[-1] - rng.uniform(C.COKING_CYCLE_HOURS_MIN, C.COKING_CYCLE_HOURS_MAX))
    times.reverse()
    while times[-1] < sim_hours + mean_cycle:
        times.append(times[-1] + rng.uniform(C.COKING_CYCLE_HOURS_MIN, C.COKING_CYCLE_HOURS_MAX))
    return np.array(times)


def _time_since_charge(t_hours: np.ndarray, schedule: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """For each timestamp, hours since the most recent charge and the
    duration of that charge's cycle (time to the *next* charge)."""
    idx = np.searchsorted(schedule, t_hours, side="right") - 1
    charge_time = schedule[idx]
    next_charge = schedule[idx + 1]
    return t_hours - charge_time, next_charge - charge_time


def _gas_temp_curve(time_since_charge: np.ndarray, cycle_duration: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    decay_rate = _LOG_20 / cycle_duration
    curve = C.GAS_TEMP_FLOOR_C + (C.GAS_TEMP_CHARGE_C - C.GAS_TEMP_FLOOR_C) * np.exp(-decay_rate * time_since_charge)
    noise = rng.normal(0.0, 8.0, size=curve.shape)
    return np.clip(curve + noise, 50.0, 850.0)


def _baseline_co(time_since_charge: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    charging_bump = 12.0 * np.exp(-time_since_charge / 0.3)
    noise = rng.normal(0.0, 2.5, size=time_since_charge.shape)
    return np.clip(8.0 + charging_bump + noise, 1.0, 35.0)


def _baseline_lel(time_since_charge: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    charging_bump = 1.5 * np.exp(-time_since_charge / 0.3)
    noise = rng.normal(0.0, 0.3, size=time_since_charge.shape)
    return np.clip(0.8 + charging_bump + noise, 0.05, 3.5)


def _spike_profile(
    t_hours: np.ndarray,
    window: RiskWindow,
    baseline: float,
    peak: float,
    rng: np.random.Generator,
    ramp_frac: float = 0.25,
) -> tuple[np.ndarray, np.ndarray]:
    """Trapezoid ramp-up/plateau/ramp-down spike shape over a window, plus its mask."""
    mask = (t_hours >= window.start_hour) & (t_hours < window.end_hour)
    duration = window.end_hour - window.start_hour
    ramp = duration * ramp_frac
    t_rel = t_hours[mask] - window.start_hour

    value = np.where(
        t_rel < ramp,
        baseline + (peak - baseline) * (t_rel / ramp),
        np.where(
            t_rel > duration - ramp,
            baseline + (peak - baseline) * ((duration - t_rel) / ramp),
            peak,
        ),
    )
    noise = rng.normal(0.0, abs(peak) * 0.03, size=value.shape)
    return mask, np.clip(value + noise, 0.0, None)


def generate(
    n_ovens: int = C.N_OVENS,
    sim_hours: int = C.SIM_HOURS,
    interval_min: int = C.SAMPLE_INTERVAL_MIN,
    seed: int = C.RANDOM_SEED,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Returns (sensor_readings_df, permit_log_df, ground_truth_df)."""
    rng = np.random.default_rng(seed)
    timestamps = _timestamps(sim_hours, interval_min)
    t_hours = _t_hours(timestamps)
    zone_of = oven_to_zone_map(n_ovens)
    zones = sorted(set(zone_of.values()))

    zone_exhauster = {z: np.full(len(timestamps), ExhausterStatus.NORMAL.value, dtype=object) for z in zones}
    for window in WINDOWS:
        if window.exhauster_fault:
            zone = zone_of[window.oven_id]
            mask = (t_hours >= window.start_hour) & (t_hours < window.end_hour)
            zone_exhauster[zone][mask] = ExhausterStatus.FAULT.value

    windows_by_oven: dict[str, list[RiskWindow]] = {}
    for window in WINDOWS:
        windows_by_oven.setdefault(window.oven_id, []).append(window)

    sensor_frames = []
    for i in range(1, n_ovens + 1):
        oid = oven_id(i)
        schedule = _charge_schedule(rng, i, n_ovens, sim_hours)
        since_charge, cycle_duration = _time_since_charge(t_hours, schedule)

        gas_temp = _gas_temp_curve(since_charge, cycle_duration, rng)
        co_ppm = _baseline_co(since_charge, rng)
        lel_pct = _baseline_lel(since_charge, rng)
        maintenance_flag = rng.random(len(timestamps)) < 0.0005

        for window in windows_by_oven.get(oid, []):
            if window.gas is not None:
                if window.gas.driver in ("co", "both"):
                    mask, values = _spike_profile(t_hours, window, 8.0, window.gas.co_peak_ppm, rng)
                    co_ppm[mask] = values
                if window.gas.driver in ("lel", "both"):
                    mask, values = _spike_profile(t_hours, window, 0.8, window.gas.lel_peak_pct, rng)
                    lel_pct[mask] = values
            if window.maintenance_flag:
                mask = (t_hours >= window.start_hour) & (t_hours < window.end_hour)
                maintenance_flag[mask] = True

        exhauster_status = zone_exhauster[zone_of[oid]]

        sensor_frames.append(
            pd.DataFrame(
                {
                    "timestamp": timestamps,
                    "oven_id": oid,
                    "gas_temp_c": gas_temp,
                    "co_ppm": co_ppm,
                    "combustible_gas_pct_lel": lel_pct,
                    "exhauster_status": exhauster_status,
                    "maintenance_flag": maintenance_flag,
                }
            )
        )

    sensor_df = pd.concat(sensor_frames, ignore_index=True)

    permit_rows = []
    permit_seq = 1

    for i in range(1, n_ovens + 1):
        oid = oven_id(i)
        n_baseline_permits = rng.integers(2, 4)
        for _ in range(n_baseline_permits):
            start_hour = rng.uniform(0, sim_hours - 4)
            duration = rng.uniform(1.0, 4.0)
            permit_rows.append(
                {
                    "permit_id": f"P{permit_seq:04d}",
                    "oven_id": oid,
                    "permit_type": "cold_work",
                    "status": PermitStatus.ACTIVE.value,
                    "issued_time": C.SIM_START + pd.Timedelta(hours=start_hour),
                    "valid_until": C.SIM_START + pd.Timedelta(hours=start_hour + duration),
                }
            )
            permit_seq += 1

    for window in WINDOWS:
        if window.permit is not None:
            permit_rows.append(
                {
                    "permit_id": f"P{permit_seq:04d}",
                    "oven_id": window.oven_id,
                    "permit_type": window.permit.permit_type,
                    "status": window.permit.status,
                    "issued_time": C.SIM_START + pd.Timedelta(hours=window.start_hour - 0.25),
                    "valid_until": C.SIM_START + pd.Timedelta(hours=window.end_hour + 0.25),
                }
            )
            permit_seq += 1

    permit_df = pd.DataFrame(permit_rows)

    ground_truth_df = pd.DataFrame(
        [
            {
                "window_id": w.window_id,
                "oven_id": w.oven_id,
                "start_time": C.SIM_START + pd.Timedelta(hours=w.start_hour),
                "end_time": C.SIM_START + pd.Timedelta(hours=w.end_hour),
                "kind": w.kind,
                "should_flag": w.should_flag,
                "description": w.description,
            }
            for w in WINDOWS
        ]
    )

    return sensor_df, permit_df, ground_truth_df
