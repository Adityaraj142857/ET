"""Static tables: Oven Registry (4.1) and Zone/Layout (4.4)."""

from __future__ import annotations

import pandas as pd

from compoundrisk.constants import (
    BATTERY_ID,
    COAL_CHARGE_TONS,
    N_OVENS,
    OVEN_VOLUME_M3,
    OVENS_PER_ZONE,
)
from compoundrisk.schemas import ZoneType


OVEN_SPACING_M = 5.0


def oven_id(index: int, battery_id: str = BATTERY_ID) -> str:
    """1-indexed oven id, e.g. B1-O01 .. B1-O67."""
    return f"{battery_id}-O{index:02d}"


def oven_x_position(index: int, spacing_m: float = OVEN_SPACING_M) -> float:
    """x-coordinate (meters) for oven `index` (1-based) along the elongated
    battery row. The single source of truth for oven spacing — zone centers
    (build_zone_layout) and individual oven positions (build_oven_positions,
    used only by the Phase-4 3D scene) both derive from this so they can
    never drift apart."""
    return index * spacing_m


def zone_id_for_oven_index(index: int, battery_id: str = BATTERY_ID) -> str:
    """Ovens 1..67 grouped into contiguous zones of ~OVENS_PER_ZONE."""
    zone_number = (index - 1) // OVENS_PER_ZONE + 1
    return f"{battery_id}-Z{zone_number:02d}"


def build_oven_registry(n_ovens: int = N_OVENS, battery_id: str = BATTERY_ID) -> pd.DataFrame:
    """Section 4.1 — static oven registry for one battery."""
    rows = [
        {
            "oven_id": oven_id(i, battery_id),
            "battery_id": battery_id,
            "volume_m3": OVEN_VOLUME_M3,
            "coal_charge_tons": COAL_CHARGE_TONS,
        }
        for i in range(1, n_ovens + 1)
    ]
    return pd.DataFrame(rows)


def build_zone_layout(n_ovens: int = N_OVENS, battery_id: str = BATTERY_ID) -> pd.DataFrame:
    """Section 4.4 — static zone/layout table feeding the future 3D heatmap.

    The battery is laid out as a single elongated row of ovens along the
    x-axis, split into contiguous zones of ~OVENS_PER_ZONE ovens each.
    Coal Chemical Plant and Exhauster House are added as separate,
    non-oven zones offset from the battery row (their coordinates matter
    only for the Phase-4 3D scene, not for this phase's risk logic).
    """
    rows = []
    zone_numbers = sorted({(i - 1) // OVENS_PER_ZONE + 1 for i in range(1, n_ovens + 1)})
    for zone_number in zone_numbers:
        start = (zone_number - 1) * OVENS_PER_ZONE + 1
        end = min(zone_number * OVENS_PER_ZONE, n_ovens)
        center_x = (oven_x_position(start) + oven_x_position(end)) / 2
        rows.append(
            {
                "zone_id": f"{battery_id}-Z{zone_number:02d}",
                "x": center_x,
                "y": 0.0,
                "z": 0.0,
                "zone_type": ZoneType.OVEN_BATTERY.value,
            }
        )

    battery_span_m = n_ovens * OVEN_SPACING_M
    rows.append(
        {
            "zone_id": "COAL-CHEM-PLANT",
            "x": battery_span_m / 2,
            "y": 40.0,
            "z": 0.0,
            "zone_type": ZoneType.COAL_CHEMICAL_PLANT.value,
        }
    )
    rows.append(
        {
            "zone_id": "EXHAUSTER-HOUSE",
            "x": battery_span_m + 20.0,
            "y": 0.0,
            "z": 0.0,
            "zone_type": ZoneType.EXHAUSTER_HOUSE.value,
        }
    )
    return pd.DataFrame(rows)


def build_oven_positions(n_ovens: int = N_OVENS, battery_id: str = BATTERY_ID) -> pd.DataFrame:
    """Individual oven 3D positions for the Phase-4 scene.

    Deliberately NOT part of the Section 4.1 oven registry schema (which
    stays oven_id/battery_id/volume_m3/coal_charge_tons, exactly as spec'd)
    — kept as a separate, frontend-only table so the canonical registry
    table isn't extended with visualization-only fields.
    """
    rows = [
        {
            "oven_id": oven_id(i, battery_id),
            "zone_id": zone_id_for_oven_index(i, battery_id),
            "x": oven_x_position(i),
            "y": 0.0,
            "z": 0.0,
        }
        for i in range(1, n_ovens + 1)
    ]
    return pd.DataFrame(rows)


def oven_to_zone_map(n_ovens: int = N_OVENS, battery_id: str = BATTERY_ID) -> dict[str, str]:
    """oven_id -> zone_id, for joining sensor readings to a shared exhauster/zone."""
    return {
        oven_id(i, battery_id): zone_id_for_oven_index(i, battery_id)
        for i in range(1, n_ovens + 1)
    }
