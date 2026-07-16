from __future__ import annotations

from compoundrisk.constants import N_OVENS, OVENS_PER_ZONE
from compoundrisk.registry import build_oven_registry, build_zone_layout, oven_to_zone_map


def test_oven_registry_has_67_ovens_with_real_plant_constants():
    df = build_oven_registry()
    assert len(df) == N_OVENS
    assert df["oven_id"].is_unique
    assert (df["volume_m3"] == 41.6).all()
    assert (df["coal_charge_tons"] == 32.0).all()
    assert df["oven_id"].iloc[0] == "B1-O01"
    assert df["oven_id"].iloc[-1] == "B1-O67"


def test_zone_layout_groups_ovens_into_expected_zone_count():
    df = build_zone_layout()
    n_battery_zones = (df["zone_type"] == "oven_battery").sum()
    expected_zones = -(-N_OVENS // OVENS_PER_ZONE)  # ceil division
    assert n_battery_zones == expected_zones
    assert {"coal_chemical_plant", "exhauster_house"}.issubset(set(df["zone_type"]))


def test_oven_to_zone_map_covers_every_oven_exactly_once():
    mapping = oven_to_zone_map()
    assert len(mapping) == N_OVENS
    zone_sizes: dict[str, int] = {}
    for zone in mapping.values():
        zone_sizes[zone] = zone_sizes.get(zone, 0) + 1
    assert all(size <= OVENS_PER_ZONE for size in zone_sizes.values())
    assert sum(zone_sizes.values()) == N_OVENS
