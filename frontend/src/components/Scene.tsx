import { useMemo } from "react";
import { Canvas } from "@react-three/fiber";
import { GradientTexture, OrbitControls, Grid } from "@react-three/drei";
import * as THREE from "three";
import { useSimulationStore } from "../store/simulationStore";
import type { RiskCategoryCode } from "../types";
import { CHAMBER_DEPTH, CHAMBER_HEIGHT } from "./ovenGeometry";
import { BuildingShell } from "./BuildingShell";
import { Gantry } from "./Gantry";
import { OvenBattery } from "./OvenBattery";
import { RestrictedZones } from "./RestrictedZones";
import { RiskHeatmap } from "./RiskHeatmap";
import { SceneDetails } from "./SceneDetails";
import { Workers } from "./Workers";
import { Zones } from "./Zones";

const SKY_RADIUS = 1800;

/** Dusk-gradient sky dome (dark navy at the zenith fading to a warm horizon
 * glow) so the upper two-thirds of the frame reads as atmosphere instead of
 * flat void. A real BackSide sphere, not a screen-space sticker, so it
 * stays consistent as the user orbits. */
function SkyDome() {
  return (
    <mesh scale={SKY_RADIUS} renderOrder={-1}>
      <sphereGeometry args={[1, 24, 16]} />
      <meshBasicMaterial side={THREE.BackSide} depthWrite={false} fog={false} toneMapped={false}>
        <GradientTexture stops={[0, 0.55, 1]} colors={["#0a0e16", "#20293a", "#3d3128"]} size={512} />
      </meshBasicMaterial>
    </mesh>
  );
}

// Warm sodium-vapor-style floodlights mounted along the gantry, at these
// fractions of the battery span.
const FLOODLIGHT_FRACTIONS = [0.14, 0.5, 0.86];

export function Scene() {
  const data = useSimulationStore((s) => s.data);
  const currentStep = useSimulationStore((s) => s.currentStep);
  const selectedOvenId = useSimulationStore((s) => s.selectedOvenId);
  const selectOven = useSimulationStore((s) => s.selectOven);

  const battery = data
    ? { span: data.meta.n_ovens * data.meta.oven_spacing_m, centerX: (data.meta.n_ovens * data.meta.oven_spacing_m) / 2 }
    : { span: 300, centerX: 150 };
  const zoneDepth = CHAMBER_DEPTH + 1.6; // matches the zone footprint depth used in Zones.tsx / RestrictedZones.tsx

  // A moderate elevated 3/4 view, centered on the battery's midpoint and
  // pulled back far enough that all 67 ovens are visible end-to-end at
  // load — a tight close-up crams the row into one corner and clips both
  // ends; OrbitControls is how the user then gets closer.
  const overviewTarget: [number, number, number] = [battery.centerX, CHAMBER_HEIGHT * 1.3, 0];
  // Distance is sized for a fairly narrow canvas aspect (the side panels eat
  // a lot of viewport width, so the canvas reads closer to square than
  // 16:9) — generous on wider windows, but never clips the ends on
  // narrower ones. Elevation (Y:Z ratio) stays ~17° regardless of scale.
  const overviewCameraPosition: [number, number, number] = [
    battery.centerX,
    Math.max(90, battery.span * 0.4),
    Math.max(300, battery.span * 1.3),
  ];

  // DirectionalLight.target defaults to a detached Object3D that's never
  // part of the scene graph, so its matrixWorld never updates from (0,0,0)
  // no matter what .position gets set to afterward — the light silently
  // "aims" at the world origin instead of the battery. Rendering the target
  // explicitly via <primitive> puts it back in the normal update traversal.
  const sunTarget = useMemo(() => {
    const target = new THREE.Object3D();
    target.position.set(battery.centerX, 0, 0);
    return target;
  }, [battery.centerX]);

  const zoneRiskCategory = useMemo(() => {
    if (!data) return () => null as RiskCategoryCode | null;
    const zoneOvenIds = new Map<string, string[]>();
    for (const oven of data.ovens) {
      if (!zoneOvenIds.has(oven.zone_id)) zoneOvenIds.set(oven.zone_id, []);
      zoneOvenIds.get(oven.zone_id)!.push(oven.oven_id);
    }
    return (zoneId: string): RiskCategoryCode | null => {
      const ovenIds = zoneOvenIds.get(zoneId);
      if (!ovenIds) return null;
      let max: RiskCategoryCode = 0;
      for (const oid of ovenIds) {
        const cat = data.series[oid]?.risk_category[currentStep] ?? 0;
        if (cat > max) max = cat;
      }
      return max;
    };
  }, [data, currentStep]);

  const riskCategories = useMemo(() => {
    if (!data) return [];
    return data.ovens.map((oven) => {
      const series = data.series[oven.oven_id];
      return series ? series.risk_category[currentStep] : null;
    });
  }, [data, currentStep]);

  const riskScores = useMemo(() => {
    if (!data) return [];
    return data.ovens.map((oven) => data.series[oven.oven_id]?.risk_score[currentStep] ?? 0);
  }, [data, currentStep]);

  const restrictedZoneIds = useMemo(() => {
    const restricted = new Set<string>();
    if (!data) return restricted;
    for (const zone of data.zones) {
      const status = data.zone_status[zone.zone_id];
      if (status?.[currentStep] === 1) restricted.add(zone.zone_id);
    }
    return restricted;
  }, [data, currentStep]);

  if (!data) return null;

  return (
    <Canvas
      shadows
      camera={{ position: overviewCameraPosition, fov: 50, near: 0.5, far: 4000 }}
      onPointerMissed={() => selectOven(null)}
    >
      <SkyDome />
      <fog attach="fog" args={["#221d18", battery.span * 1.55, battery.span * 4]} />
      <hemisphereLight intensity={0.65} color="#3a4656" groundColor="#1a1512" />
      <primitive object={sunTarget} />
      <directionalLight
        position={[battery.centerX, 90, 60]}
        target={sunTarget}
        intensity={2.4}
        color="#fff3e2"
        castShadow
        shadow-mapSize={[2048, 2048]}
        shadow-camera-left={-battery.span / 2 - 30}
        shadow-camera-right={battery.span / 2 + 30}
        shadow-camera-top={70}
        shadow-camera-bottom={-20}
        shadow-camera-near={1}
        shadow-camera-far={400}
      />
      <ambientLight intensity={0.4} />
      {FLOODLIGHT_FRACTIONS.map((f) => (
        <pointLight
          key={f}
          position={[battery.centerX - battery.span / 2 + battery.span * f, CHAMBER_HEIGHT + 3.5, 0]}
          color="#ff9d4d"
          intensity={550}
          distance={70}
          decay={2}
          castShadow={f === 0.5}
          shadow-mapSize={[512, 512]}
        />
      ))}

      <mesh position={[battery.centerX, -0.03, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[battery.span * 4, battery.span * 4]} />
        <meshStandardMaterial color="#141412" roughness={1} metalness={0} />
      </mesh>
      <Grid
        position={[battery.centerX, 0, 0]}
        args={[battery.span * 1.6, battery.span * 1.6]}
        cellSize={5}
        cellThickness={0.5}
        cellColor="#2c2c2a"
        sectionSize={25}
        sectionThickness={1}
        sectionColor="#3a3a37"
        fadeDistance={battery.span * 1.4}
        infiniteGrid
      />

      <Zones zones={data.zones} ovens={data.ovens} chamberWidth={data.meta.oven_spacing_m} zoneRiskCategory={zoneRiskCategory} />

      <OvenBattery
        ovens={data.ovens}
        chamberWidth={data.meta.oven_spacing_m}
        riskCategories={riskCategories}
        selectedOvenId={selectedOvenId}
        onSelect={selectOven}
      />

      <RiskHeatmap
        ovens={data.ovens}
        chamberWidth={data.meta.oven_spacing_m}
        riskCategories={riskCategories}
        riskScores={riskScores}
      />

      <RestrictedZones
        ovens={data.ovens}
        zones={data.zones}
        chamberWidth={data.meta.oven_spacing_m}
        restrictedZoneIds={restrictedZoneIds}
      />

      <Gantry span={battery.span} centerX={battery.centerX} depth={zoneDepth} />
      <SceneDetails span={battery.span} centerX={battery.centerX} depth={zoneDepth} />

      <BuildingShell
        ovens={data.ovens}
        zones={data.zones}
        chamberWidth={data.meta.oven_spacing_m}
        span={battery.span}
        centerX={battery.centerX}
        depth={zoneDepth}
      />

      <Workers
        data={data}
        currentStep={currentStep}
        ovens={data.ovens}
        zones={data.zones}
        chamberWidth={data.meta.oven_spacing_m}
        zoneDepth={zoneDepth}
      />

      <OrbitControls
        target={overviewTarget}
        minDistance={10}
        maxDistance={battery.span * 3}
        maxPolarAngle={Math.PI / 2 - 0.02}
      />
    </Canvas>
  );
}
