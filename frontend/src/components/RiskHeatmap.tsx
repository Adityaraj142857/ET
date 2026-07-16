import { useEffect, useRef } from "react";
import * as THREE from "three";
import type { OvenMeta, RiskCategoryCode } from "../types";
import { CHAMBER_HEIGHT } from "./ovenGeometry";

interface RiskHeatmapProps {
  ovens: OvenMeta[];
  chamberWidth: number;
  riskCategories: (RiskCategoryCode | null)[]; // aligned to ovens[]
  riskScores: number[]; // aligned to ovens[], continuous 0-1
}

const HEAT_RED = "208,59,59"; // STATUS_COLOR.high, as an rgb() triple for canvas gradients
const HEAT_YELLOW = "250,178,25"; // STATUS_COLOR.medium

const MIN_SIZE_FACTOR = 2.2;
const MAX_SIZE_FACTOR = 5.0;
const MIN_OPACITY = 0.35;
const MAX_OPACITY = 0.85;

/** A wifi-heatmap-style radial gradient (red core -> yellow ring ->
 * transparent) baked into a canvas texture. The red core's reach and
 * brightness grow with `t` so higher-risk sprites read as denser/redder
 * blooms and lower-risk ones read as smaller, mostly-yellow ones — not just
 * a uniform-color sprite scaled up or down. */
function buildHeatTexture(t: number): THREE.CanvasTexture {
  const size = 128;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  const cx = size / 2;
  const cy = size / 2;
  const coreStop = 0.15 + t * 0.35; // red core radius fraction: 0.15 -> 0.5
  const midStop = Math.min(0.55 + t * 0.25, 0.85); // yellow ring reach: 0.55 -> 0.8
  const coreAlpha = 0.55 + t * 0.45; // 0.55 -> 1

  const gradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, size / 2);
  gradient.addColorStop(0, `rgba(${HEAT_RED},${coreAlpha})`);
  gradient.addColorStop(coreStop, `rgba(${HEAT_RED},${coreAlpha * 0.85})`);
  gradient.addColorStop(midStop, `rgba(${HEAT_YELLOW},${0.5 + t * 0.2})`);
  gradient.addColorStop(1, `rgba(${HEAT_YELLOW},0)`);

  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, size, size);

  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  return texture;
}

/** Buckets risk_score to the nearest 0.1 so the handful of simultaneously
 * flagged ovens share a small pool of cached textures instead of each
 * generating (and disposing) its own canvas every timeline step. */
function bucket(t: number): number {
  return Math.round(THREE.MathUtils.clamp(t, 0, 1) * 10) / 10;
}

/** Sprite-based radial heatmap bloom for ovens at medium/high risk — a wifi
 * signal-strength-style visualization layered above the battery, not a
 * shader-based heat diffusion system. Gated on risk_category (medium/high)
 * rather than a raw risk_score cutoff: the rule engine deliberately treats
 * category as "which conditions are present", not a score threshold (see
 * rule_engine.py) — a compound-risk two-of-three case can score lower than
 * a single maxed-out gas reading, so a score cutoff here would silently
 * miss/misrepresent exactly the cases this tool exists to surface. Score is
 * still used, continuously, to size/color each bloom once an oven qualifies. */
export function RiskHeatmap({ ovens, chamberWidth, riskCategories, riskScores }: RiskHeatmapProps) {
  const textureCache = useRef(new Map<number, THREE.CanvasTexture>());

  useEffect(() => {
    const cache = textureCache.current;
    return () => {
      cache.forEach((tex) => tex.dispose());
      cache.clear();
    };
  }, []);

  const minSize = chamberWidth * MIN_SIZE_FACTOR;
  const maxSize = chamberWidth * MAX_SIZE_FACTOR;

  return (
    <group>
      {ovens.map((oven, i) => {
        const category = riskCategories[i];
        if (category === null || category === undefined || category === 0) return null;

        const score = riskScores[i] ?? 0;
        // Normalize within the band medium+ scores actually occupy (a bare
        // single-factor medium can score as low as ~0.25) so the low end of
        // that band still reads as a visible-but-small bloom, not near-zero.
        const t = THREE.MathUtils.clamp((score - 0.2) / 0.8, 0, 1);

        const key = bucket(t);
        let texture = textureCache.current.get(key);
        if (!texture) {
          texture = buildHeatTexture(key);
          textureCache.current.set(key, texture);
        }

        const size = minSize + t * (maxSize - minSize);
        const opacity = MIN_OPACITY + t * (MAX_OPACITY - MIN_OPACITY);

        return (
          <sprite
            key={oven.oven_id}
            position={[oven.x, CHAMBER_HEIGHT + 1.5 + size * 0.25, oven.z]}
            scale={[size, size, 1]}
            renderOrder={1}
          >
            <spriteMaterial
              map={texture}
              opacity={opacity}
              transparent
              depthWrite={false}
              blending={THREE.AdditiveBlending}
            />
          </sprite>
        );
      })}
    </group>
  );
}
