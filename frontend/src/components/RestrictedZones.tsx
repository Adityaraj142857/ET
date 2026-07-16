import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import type { OvenMeta, ZoneMeta } from "../types";
import { CHAMBER_DEPTH, zoneFootprints } from "./ovenGeometry";

const BARRIER_HEIGHT = 2.2;
const BARRIER_THICKNESS = 0.15;
const STRIPE_UNIT_M = 3; // ~1 stripe repeat per 3m, so tape reads at a consistent physical scale across different-length edges
const ZONE_DEPTH = CHAMBER_DEPTH + 1.6; // matches the zone risk-wireframe box depth in Zones.tsx

interface RestrictedZonesProps {
  ovens: OvenMeta[];
  zones: ZoneMeta[];
  chamberWidth: number;
  restrictedZoneIds: Set<string>;
}

/** 45-degree red/black hazard-tape texture, tileable via RepeatWrapping. */
function buildHazardStripeTexture(): THREE.CanvasTexture {
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d")!;

  ctx.fillStyle = "#141210";
  ctx.fillRect(0, 0, size, size);
  ctx.fillStyle = "#d03b3b";
  const bandWidth = size / 4;
  ctx.save();
  ctx.translate(size / 2, size / 2);
  ctx.rotate(Math.PI / 4);
  ctx.translate(-size, -size);
  for (let x = -size; x < size * 3; x += bandWidth * 2) {
    ctx.fillRect(x, -size, bandWidth, size * 4);
  }
  ctx.restore();

  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.needsUpdate = true;
  return texture;
}

/** Hazard-tape perimeter around each currently-RESTRICTED zone's footprint —
 * a distinct "entry is blocked here" signal, kept visually separate from
 * the risk heatmap's soft red/yellow blooms (RiskHeatmap.tsx). Deliberately
 * opaque, static, and geometric rather than a soft additive glow: one is a
 * live hazard reading, the other is a hard access-control boundary, and
 * they should not be mistakable for each other. */
export function RestrictedZones({ ovens, zones, chamberWidth, restrictedZoneIds }: RestrictedZonesProps) {
  const textureCache = useRef(new Map<number, THREE.CanvasTexture>());

  useEffect(() => {
    const cache = textureCache.current;
    return () => {
      cache.forEach((tex) => tex.dispose());
      cache.clear();
    };
  }, []);

  const footprints = useMemo(() => zoneFootprints(ovens, chamberWidth), [ovens, chamberWidth]);

  const getTexture = (length: number): THREE.CanvasTexture => {
    const repeatCount = Math.max(1, Math.round(length / STRIPE_UNIT_M));
    let tex = textureCache.current.get(repeatCount);
    if (!tex) {
      tex = buildHazardStripeTexture();
      tex.repeat.set(repeatCount, 1);
      textureCache.current.set(repeatCount, tex);
    }
    return tex;
  };

  const restrictedZones = zones.filter((z) => z.zone_type === "oven_battery" && restrictedZoneIds.has(z.zone_id));

  return (
    <group>
      {restrictedZones.map((zone) => {
        const footprint = footprints.get(zone.zone_id);
        if (!footprint) return null;
        const { centerX, width } = footprint;

        return (
          <group key={zone.zone_id}>
            <mesh position={[centerX, BARRIER_HEIGHT / 2, ZONE_DEPTH / 2]}>
              <boxGeometry args={[width, BARRIER_HEIGHT, BARRIER_THICKNESS]} />
              <meshBasicMaterial map={getTexture(width)} toneMapped={false} />
            </mesh>
            <mesh position={[centerX, BARRIER_HEIGHT / 2, -ZONE_DEPTH / 2]}>
              <boxGeometry args={[width, BARRIER_HEIGHT, BARRIER_THICKNESS]} />
              <meshBasicMaterial map={getTexture(width)} toneMapped={false} />
            </mesh>
            <mesh position={[centerX - width / 2, BARRIER_HEIGHT / 2, 0]}>
              <boxGeometry args={[BARRIER_THICKNESS, BARRIER_HEIGHT, ZONE_DEPTH]} />
              <meshBasicMaterial map={getTexture(ZONE_DEPTH)} toneMapped={false} />
            </mesh>
            <mesh position={[centerX + width / 2, BARRIER_HEIGHT / 2, 0]}>
              <boxGeometry args={[BARRIER_THICKNESS, BARRIER_HEIGHT, ZONE_DEPTH]} />
              <meshBasicMaterial map={getTexture(ZONE_DEPTH)} toneMapped={false} />
            </mesh>
          </group>
        );
      })}
    </group>
  );
}
