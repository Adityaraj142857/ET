import { useMemo } from "react";
import { Text } from "@react-three/drei";
import type { OvenMeta, RiskCategoryCode, ZoneMeta } from "../types";
import { RISK_CATEGORY_NAME, STATUS_GLYPH } from "../utils/color";
import { CHAMBER_DEPTH, CHAMBER_HEIGHT, zoneFootprints } from "./ovenGeometry";

// Neutral steel-toned zone boundary — deliberately NOT colored by risk
// category. Risk color belongs on the per-oven beacon (OvenBattery.tsx) and
// the restricted-zone hazard barrier (RestrictedZones.tsx); a zone-wide
// colored wireframe box on top of those was exactly the "flat, colorful
// technical sketch" look the Prompt 4 materials pass exists to remove. The
// zone's status is still legible from the glyph in its label text.
const ZONE_OUTLINE_COLOR = "#4a453c";

interface ZonesProps {
  zones: ZoneMeta[];
  ovens: OvenMeta[];
  chamberWidth: number;
  zoneRiskCategory: (zoneId: string) => RiskCategoryCode | null;
}

/** Zone grouping (Section 6, "recommended"): a translucent outline around
 * each ~10-oven cluster with a zone-level aggregate status, so the battery
 * reads as a structured plant, not just 67 anonymous blocks in a row. Plus
 * schematic landmarks for the two non-oven zone types, for spatial context. */
export function Zones({ zones, ovens, chamberWidth, zoneRiskCategory }: ZonesProps) {
  const footprints = useMemo(() => zoneFootprints(ovens, chamberWidth), [ovens, chamberWidth]);

  return (
    <group>
      {zones
        .filter((z) => z.zone_type === "oven_battery")
        .map((zone) => {
          const footprint = footprints.get(zone.zone_id);
          if (!footprint) return null;
          const { centerX, width } = footprint;
          const category = zoneRiskCategory(zone.zone_id);
          const categoryName = category === null ? null : RISK_CATEGORY_NAME[category];

          return (
            <group key={zone.zone_id}>
              <mesh position={[centerX, CHAMBER_HEIGHT / 2, 0]}>
                <boxGeometry args={[width, CHAMBER_HEIGHT + 1.2, CHAMBER_DEPTH + 1.6]} />
                <meshBasicMaterial color={ZONE_OUTLINE_COLOR} wireframe transparent opacity={0.18} />
              </mesh>
              <Text
                position={[centerX, CHAMBER_HEIGHT + 2.4, 0]}
                fontSize={1.0}
                color="#c3c2b7"
                anchorX="center"
                anchorY="middle"
              >
                {`${zone.zone_id}${categoryName ? "  " + STATUS_GLYPH[categoryName] : ""}`}
              </Text>
            </group>
          );
        })}

      {zones
        .filter((z) => z.zone_type !== "oven_battery")
        .map((zone) => (
          <PlantLandmark key={zone.zone_id} zone={zone} />
        ))}
    </group>
  );
}

function PlantLandmark({ zone }: { zone: ZoneMeta }) {
  const label = zone.zone_type === "coal_chemical_plant" ? "Coal Chemical Plant" : "Exhauster House";
  const size: [number, number, number] = zone.zone_type === "coal_chemical_plant" ? [26, 9, 16] : [10, 6, 10];

  return (
    <group position={[zone.x, zone.y, zone.z]}>
      <mesh position={[0, size[1] / 2, 0]} castShadow receiveShadow>
        <boxGeometry args={size} />
        <meshStandardMaterial color="#33332f" roughness={0.8} metalness={0.1} />
      </mesh>
      <Text position={[0, size[1] + 1.2, 0]} fontSize={1.1} color="#898781" anchorX="center" anchorY="middle">
        {label}
      </Text>
    </group>
  );
}
