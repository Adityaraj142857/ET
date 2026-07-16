import { useMemo } from "react";
import * as THREE from "three";
import type { OvenMeta, ZoneMeta } from "../types";
import { zoneFootprints } from "./ovenGeometry";

interface BuildingShellProps {
  ovens: OvenMeta[];
  zones: ZoneMeta[];
  chamberWidth: number;
  span: number;
  centerX: number;
  depth: number; // zone footprint depth (chamber row's Z extent)
}

const WALL_THICKNESS = 0.3;
const ROOF_THICKNESS = 0.4;
const ROOF_HEIGHT = 15; // clears the gantry rail deck (CHAMBER_HEIGHT + 1.8 ~= 8.8m) with margin
const SIDE_MARGIN = 6; // interior past the row's ends, inside the end walls
const BACK_MARGIN = 4; // behind the chamber/gantry footprint
const AISLE_DEPTH = 14; // open walking area in front, toward the camera
const DOOR_WIDTH = 12;
const BEAM_SPACING = 22;

const WALL_COLOR = "#28251f";
const ROOF_COLOR = "#3c4048";
const FLOOR_COLOR = "#2b2824";
const BEAM_COLOR = "#302c26";

interface Segment {
  center: number;
  width: number;
}

/** Splits [minX, maxX] into wall segments, leaving a full-height gap at
 * each entry in `gaps` — the simplest way to represent door openings with
 * flat box panels instead of a real CSG cutout. */
function segmentsWithGaps(minX: number, maxX: number, gaps: Segment[]): Segment[] {
  const sorted = [...gaps].sort((a, b) => a.center - b.center);
  const segments: Segment[] = [];
  let cursor = minX;
  for (const gap of sorted) {
    const gapMin = gap.center - gap.width / 2;
    const gapMax = gap.center + gap.width / 2;
    if (gapMin > cursor) segments.push({ center: (cursor + gapMin) / 2, width: gapMin - cursor });
    cursor = Math.max(cursor, gapMax);
  }
  if (cursor < maxX) segments.push({ center: (cursor + maxX) / 2, width: maxX - cursor });
  return segments;
}

/** A simple three-sided industrial shed enclosing the battery: solid-ish
 * back and end walls, an open front (so the camera and OrbitControls keep
 * full access), and translucent wall/roof panels — reads as "inside a
 * factory hall" without ever fully hiding the battery, heatmap, or worker
 * figures from any orbit angle, and without blocking the directional "sun"
 * light the Prompt-4 lighting pass depends on. A couple of full-height
 * bay-door gaps in the back wall, positioned at existing zone boundaries,
 * stand in for zone entry points. Purely decorative: no data logic here. */
export function BuildingShell({ ovens, zones, chamberWidth, span, centerX, depth }: BuildingShellProps) {
  const footprints = useMemo(() => zoneFootprints(ovens, chamberWidth), [ovens, chamberWidth]);

  const startX = centerX - span / 2 - SIDE_MARGIN;
  const endX = centerX + span / 2 + SIDE_MARGIN;
  const backZ = -depth / 2 - BACK_MARGIN;
  const frontZ = depth / 2 + AISLE_DEPTH;
  const buildingDepth = frontZ - backZ;
  const centerZ = (backZ + frontZ) / 2;

  const doorGaps = useMemo<Segment[]>(() => {
    const batteryZones = zones
      .filter((z) => z.zone_type === "oven_battery")
      .slice()
      .sort((a, b) => a.zone_id.localeCompare(b.zone_id));
    if (batteryZones.length === 0) return [];
    const rawIndices = [Math.floor(batteryZones.length * 0.25), Math.floor(batteryZones.length * 0.75)];
    const indices = Array.from(new Set(rawIndices.map((i) => Math.min(i, batteryZones.length - 1))));
    return indices
      .map((i) => {
        const fp = footprints.get(batteryZones[i].zone_id);
        return fp ? { center: fp.centerX, width: DOOR_WIDTH } : null;
      })
      .filter((g): g is Segment => g !== null);
  }, [zones, footprints]);

  const backWallSegments = useMemo(() => segmentsWithGaps(startX, endX, doorGaps), [startX, endX, doorGaps]);

  const beamCount = Math.max(0, Math.floor((endX - startX) / BEAM_SPACING) - 1);

  return (
    <group>
      {backWallSegments.map((seg) => (
        <mesh key={seg.center} position={[seg.center, ROOF_HEIGHT / 2, backZ]}>
          <boxGeometry args={[seg.width, ROOF_HEIGHT, WALL_THICKNESS]} />
          <meshStandardMaterial
            color={WALL_COLOR}
            roughness={0.9}
            metalness={0.1}
            transparent
            opacity={0.55}
            side={THREE.DoubleSide}
            depthWrite={false}
          />
        </mesh>
      ))}

      {/* Door-frame posts — just for visual definition around each opening. */}
      {doorGaps.map((gap) =>
        [-1, 1].map((side) => (
          <mesh key={`${gap.center}-${side}`} position={[gap.center + (side * gap.width) / 2, ROOF_HEIGHT / 2, backZ]} castShadow>
            <boxGeometry args={[0.4, ROOF_HEIGHT, 0.5]} />
            <meshStandardMaterial color={BEAM_COLOR} roughness={0.6} metalness={0.5} />
          </mesh>
        ))
      )}

      {[startX, endX].map((x) => (
        <mesh key={x} position={[x, ROOF_HEIGHT / 2, centerZ]}>
          <boxGeometry args={[WALL_THICKNESS, ROOF_HEIGHT, buildingDepth]} />
          <meshStandardMaterial
            color={WALL_COLOR}
            roughness={0.9}
            metalness={0.1}
            transparent
            opacity={0.55}
            side={THREE.DoubleSide}
            depthWrite={false}
          />
        </mesh>
      ))}

      {/* Roof — translucent skylight-style panels, so it reads as an
          enclosing roof without shadowing out the directional sun light
          the rest of the scene's lighting relies on. */}
      <mesh position={[centerX, ROOF_HEIGHT + ROOF_THICKNESS / 2, centerZ]}>
        <boxGeometry args={[endX - startX, ROOF_THICKNESS, buildingDepth]} />
        <meshStandardMaterial
          color={ROOF_COLOR}
          roughness={0.7}
          metalness={0.2}
          transparent
          opacity={0.4}
          side={THREE.DoubleSide}
          depthWrite={false}
        />
      </mesh>

      {Array.from({ length: beamCount }, (_, i) => {
        const x = startX + BEAM_SPACING * (i + 1);
        return (
          <mesh key={x} position={[x, ROOF_HEIGHT - 0.25, centerZ]} castShadow>
            <boxGeometry args={[0.35, 0.5, buildingDepth]} />
            <meshStandardMaterial color={BEAM_COLOR} roughness={0.5} metalness={0.6} />
          </mesh>
        );
      })}

      {/* Interior floor — a distinct facility tone, sitting just above the
          outdoor ground plane it overlaps. */}
      <mesh position={[centerX, 0.02, centerZ]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[endX - startX, buildingDepth]} />
        <meshStandardMaterial color={FLOOR_COLOR} roughness={0.95} metalness={0.05} />
      </mesh>
    </group>
  );
}
