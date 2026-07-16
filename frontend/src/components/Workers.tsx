import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import type { OvenMeta, ScenePayload, WorkerEvent, ZoneMeta } from "../types";
import { STATUS_COLOR } from "../utils/color";
import { zoneFootprints } from "./ovenGeometry";

interface WorkersProps {
  data: ScenePayload;
  currentStep: number;
  ovens: OvenMeta[];
  zones: ZoneMeta[];
  chamberWidth: number;
  zoneDepth: number;
}

const NORMAL_COLOR = "#6b7c8c";
const WARNED_COLOR = STATUS_COLOR.medium;
const BLOCKED_COLOR = STATUS_COLOR.high;

// A worker's color reflects their MOST RECENT event only while it's still
// "fresh" — this is a simulation-step window, not a wall-clock timer, so it
// stays correct under manual scrubbing (not just autoplay). It's a rough
// stand-in for "a few seconds," not a literal one; see the module docstring
// below for why an exact real-time match isn't practical here.
const EVENT_DISPLAY_STEPS = 12;

const BODY_RADIUS = 0.22;
const BODY_LENGTH = 0.9;
const HEAD_RADIUS = 0.16;
const LANE_COUNT = 4;
const LANE_SPACING = 1.5;

interface WorkerVisualState {
  workerId: string;
  x: number;
  z: number;
  color: string;
  warned: boolean;
}

/** Zone-level worker figures — capsule body + sphere head, no rigging or
 * pathfinding. Each worker's displayed zone, and whether they're currently
 * shown "warned" (yellow, glowing ring) or "blocked" (red, parked at the
 * threshold of the zone they were denied entry to) is a pure function of
 * `currentStep` against the existing worker_zones/events data from Prompt
 * 3 — same "scrub the timeline, everything updates" architecture as the
 * oven risk colors and heatmap sprites. This component only visualizes
 * that data; it never computes zone status or restriction decisions. */
export function Workers({ data, currentStep, ovens, zones, chamberWidth, zoneDepth }: WorkersProps) {
  const footprints = useMemo(() => zoneFootprints(ovens, chamberWidth), [ovens, chamberWidth]);

  const zoneAnchor = useMemo(() => {
    const map = new Map<string, { x: number; z: number }>();
    for (const [zoneId, fp] of footprints) map.set(zoneId, { x: fp.centerX, z: 0 });
    for (const zone of zones) if (!map.has(zone.zone_id)) map.set(zone.zone_id, { x: zone.x, z: zone.z });
    return map;
  }, [footprints, zones]);

  // Most recent event at or before currentStep, per worker.
  const latestEventByWorker = useMemo(() => {
    const map = new Map<string, WorkerEvent>();
    for (const event of data.events) {
      if (event.step > currentStep) continue;
      const existing = map.get(event.worker_id);
      if (!existing || event.step > existing.step) map.set(event.worker_id, event);
    }
    return map;
  }, [data.events, currentStep]);

  const workerStates = useMemo<WorkerVisualState[]>(() => {
    return data.workers.map((worker, i) => {
      const currentZoneId = data.worker_zones[worker.worker_id]?.[currentStep];
      const latest = latestEventByWorker.get(worker.worker_id);
      const isFresh = !!latest && currentStep - latest.step <= EVENT_DISPLAY_STEPS;

      let anchorZoneId = currentZoneId;
      let color = NORMAL_COLOR;
      let warned = false;
      let stoppedAtThreshold = false;

      if (isFresh && latest!.event_type === "warning_issued") {
        color = WARNED_COLOR;
        warned = true;
      } else if (isFresh && latest!.event_type === "entry_blocked") {
        color = BLOCKED_COLOR;
        // Denied entry — shown parked at the doorway of the zone they tried
        // to enter, not inside it (their actual current_zone_id is
        // unchanged in the underlying data; this is a display-only stand-in).
        anchorZoneId = latest!.zone_id;
        stoppedAtThreshold = true;
      }

      const anchor = (anchorZoneId && zoneAnchor.get(anchorZoneId)) || { x: 0, z: 0 };
      const lane = i % LANE_COUNT;
      const jitterX = (lane - (LANE_COUNT - 1) / 2) * LANE_SPACING;
      const aisleZ = stoppedAtThreshold ? zoneDepth / 2 + 0.6 : zoneDepth / 2 + 3 + (i % 3) * 1.8;

      return {
        workerId: worker.worker_id,
        x: anchor.x + jitterX,
        z: anchor.z + aisleZ,
        color,
        warned,
      };
    });
  }, [data.workers, data.worker_zones, currentStep, latestEventByWorker, zoneAnchor, zoneDepth]);

  return (
    <group>
      {workerStates.map((state) => (
        <WorkerFigure key={state.workerId} state={state} />
      ))}
    </group>
  );
}

function WorkerFigure({ state }: { state: WorkerVisualState }) {
  const ringRef = useRef<THREE.Mesh>(null);
  const color = useMemo(() => new THREE.Color(state.color), [state.color]);

  useFrame(({ clock }) => {
    const ring = ringRef.current;
    if (!ring) return;
    const material = ring.material as THREE.MeshBasicMaterial;
    material.opacity = 0.55 + 0.4 * Math.sin(clock.elapsedTime * 5);
    ring.rotation.z += 0.015;
  });

  return (
    <group position={[state.x, 0, state.z]}>
      <mesh position={[0, BODY_LENGTH / 2 + BODY_RADIUS, 0]} castShadow>
        <capsuleGeometry args={[BODY_RADIUS, BODY_LENGTH, 4, 8]} />
        <meshStandardMaterial color={color} roughness={0.6} metalness={0.1} />
      </mesh>
      <mesh position={[0, BODY_LENGTH + BODY_RADIUS + HEAD_RADIUS, 0]} castShadow>
        <sphereGeometry args={[HEAD_RADIUS, 12, 10]} />
        <meshStandardMaterial color={color} roughness={0.6} metalness={0.1} />
      </mesh>

      {state.warned && (
        <mesh ref={ringRef} position={[0, BODY_LENGTH + BODY_RADIUS + HEAD_RADIUS * 2 + 0.35, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.28, 0.035, 8, 24]} />
          <meshBasicMaterial color={WARNED_COLOR} transparent toneMapped={false} />
        </mesh>
      )}
    </group>
  );
}
