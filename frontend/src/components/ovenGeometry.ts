import type { OvenMeta } from "../types";

// Shared visual proportions for the oven battery wall. Chamber width is NOT
// here — it's set dynamically to data.meta.oven_spacing_m (see Scene.tsx) so
// the 67 chambers sit flush with zero gap, whatever the spacing is.
export const CHAMBER_HEIGHT = 7.0; // real fact-checked figure: 7m tall ovens (project context, "Salient features")
export const CHAMBER_DEPTH = 4.0; // push-to-coke-side chamber length; kept well below CHAMBER_HEIGHT so each
// chamber (and the wall as a whole) reads as TALL, not as a long flat curb — see the Prompt 4 materials pass

export interface ZoneFootprint {
  centerX: number;
  width: number;
}

/** X-axis footprint (center + width) of each oven_battery zone, derived
 * from its member ovens' positions — the single source of truth shared by
 * the zone risk-wireframe (Zones.tsx) and the restricted-zone hazard
 * barrier (RestrictedZones.tsx), so the two never draw different bounds
 * for the same zone. */
export function zoneFootprints(ovens: OvenMeta[], chamberWidth: number): Map<string, ZoneFootprint> {
  const xsByZone = new Map<string, number[]>();
  for (const oven of ovens) {
    if (!xsByZone.has(oven.zone_id)) xsByZone.set(oven.zone_id, []);
    xsByZone.get(oven.zone_id)!.push(oven.x);
  }

  const footprints = new Map<string, ZoneFootprint>();
  for (const [zoneId, xs] of xsByZone) {
    const minX = Math.min(...xs) - chamberWidth / 2 - 0.6;
    const maxX = Math.max(...xs) + chamberWidth / 2 + 0.6;
    footprints.set(zoneId, { centerX: (minX + maxX) / 2, width: maxX - minX });
  }
  return footprints;
}
