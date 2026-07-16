import { useEffect, useMemo, useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import type { ThreeEvent } from "@react-three/fiber";
import { Edges, Text } from "@react-three/drei";
import * as THREE from "three";
import type { OvenMeta, RiskCategoryCode } from "../types";
import { colorForCategory, PENDING_COLOR, STATUS_GLYPH, RISK_CATEGORY_NAME } from "../utils/color";
import { CHAMBER_DEPTH, CHAMBER_HEIGHT } from "./ovenGeometry";

interface OvenBatteryProps {
  ovens: OvenMeta[];
  chamberWidth: number; // == oven_spacing_m, so instances sit flush with no gaps
  riskCategories: (RiskCategoryCode | null)[]; // aligned to ovens[]
  selectedOvenId: string | null;
  onSelect: (ovenId: string | null) => void;
}

const PULSE_TARGET = new THREE.Color("#ffffff");
const tmpMatrix = new THREE.Matrix4();
const tmpColor = new THREE.Color();

// Weathered steel/rust body tones — the structure's actual material color.
// Cycled per-oven-index (not risk-driven) purely so the wall reads as an
// uneven, weathered surface rather than one flat plastic color. Risk color
// lives only on the status-light lens below, never on the body.
const BODY_TONES = ["#5a5046", "#4b443c", "#645a4e", "#544a40"];

// Status light housing (metal, same material family as the body) + a
// recessed emissive-looking lens sitting flush inside it — a status panel
// mounted on the roofline, not a floating colored pill.
const HOUSING_COLOR = "#33302b";
const HOUSING_HEIGHT = 0.22;
const HOUSING_SIZE_FACTOR = 0.55;
const LENS_HEIGHT = 0.05;
const LENS_WIDTH_FACTOR = 0.34; // narrow rectangle, not square
const LENS_DEPTH_FACTOR = 0.16;

const SELECTION_COLOR = "#5fe0ff";

/** The 67 oven chambers as one InstancedMesh — a single dense wall, not 67
 * separately-created meshes. Positions/colors are pushed onto the instance
 * buffers directly rather than driving them through per-object materials.
 *
 * Risk color is deliberately NOT the chamber body's color, nor the status
 * light's own base color. The body is a neutral weathered-steel
 * InstancedMesh; a second InstancedMesh ("housing") is a small flush metal
 * panel mounted into each chamber's roofline, in the same lit-material
 * family as the body; a third, much smaller InstancedMesh ("lens") is inset
 * into the housing's top face and carries the risk color as an unlit glow —
 * a status light recessed into the structure, not a paint job or a
 * floating colored pill. */
export function OvenBattery({ ovens, chamberWidth, riskCategories, selectedOvenId, onSelect }: OvenBatteryProps) {
  const bodyRef = useRef<THREE.InstancedMesh>(null);
  const housingRef = useRef<THREE.InstancedMesh>(null);
  const lensRef = useRef<THREE.InstancedMesh>(null);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  const bodyColors = useMemo(
    () => ovens.map((_, i) => new THREE.Color(BODY_TONES[i % BODY_TONES.length])),
    [ovens]
  );

  const lensColors = useMemo(
    () => riskCategories.map((cat) => new THREE.Color(cat === null ? PENDING_COLOR : colorForCategory(cat))),
    [riskCategories]
  );

  const highIndices = useMemo(
    () => riskCategories.reduce<number[]>((acc, cat, i) => (cat === 2 ? [...acc, i] : acc), []),
    [riskCategories]
  );

  useEffect(() => {
    const body = bodyRef.current;
    const housing = housingRef.current;
    const lens = lensRef.current;
    if (!body || !housing || !lens) return;
    const housingTopY = CHAMBER_HEIGHT + HOUSING_HEIGHT / 2;
    const lensY = housingTopY + LENS_HEIGHT / 2;
    ovens.forEach((oven, i) => {
      tmpMatrix.makeTranslation(oven.x, CHAMBER_HEIGHT / 2, oven.z);
      body.setMatrixAt(i, tmpMatrix);
      // Centered on the roofline (not sitting on top of it) so half the
      // housing embeds into the chamber and half sits proud — flush-mounted
      // rather than a block floating above the surface.
      tmpMatrix.makeTranslation(oven.x, CHAMBER_HEIGHT, oven.z);
      housing.setMatrixAt(i, tmpMatrix);
      tmpMatrix.makeTranslation(oven.x, lensY, oven.z);
      lens.setMatrixAt(i, tmpMatrix);
    });
    body.instanceMatrix.needsUpdate = true;
    housing.instanceMatrix.needsUpdate = true;
    lens.instanceMatrix.needsUpdate = true;
  }, [ovens]);

  useEffect(() => {
    const body = bodyRef.current;
    if (!body) return;
    bodyColors.forEach((color, i) => body.setColorAt(i, color));
    if (body.instanceColor) body.instanceColor.needsUpdate = true;
  }, [bodyColors]);

  useEffect(() => {
    const lens = lensRef.current;
    if (!lens) return;
    lensColors.forEach((color, i) => lens.setColorAt(i, color));
    if (lens.instanceColor) lens.instanceColor.needsUpdate = true;
  }, [lensColors]);

  // Subtle pulsing brightness on active compound-risk (high) lenses — a
  // motion cue that doesn't ride on hue alone, applied as instance color.
  useFrame(({ clock }) => {
    const lens = lensRef.current;
    if (!lens || highIndices.length === 0) return;
    const pulse = 0.55 + 0.35 * Math.sin(clock.elapsedTime * 4);
    for (const i of highIndices) {
      tmpColor.copy(lensColors[i]).lerp(PULSE_TARGET, pulse * 0.35);
      lens.setColorAt(i, tmpColor);
    }
    if (lens.instanceColor) lens.instanceColor.needsUpdate = true;
  });

  const selectedIndex = useMemo(
    () => (selectedOvenId ? ovens.findIndex((o) => o.oven_id === selectedOvenId) : -1),
    [ovens, selectedOvenId]
  );
  const labelIndex = hoveredIndex ?? (selectedIndex >= 0 ? selectedIndex : null);
  const labelOven = labelIndex !== null ? ovens[labelIndex] : null;
  const labelCategory = labelIndex !== null ? riskCategories[labelIndex] : null;

  const housingSize = chamberWidth * HOUSING_SIZE_FACTOR;
  const lensWidth = chamberWidth * LENS_WIDTH_FACTOR;
  const lensDepth = chamberWidth * LENS_DEPTH_FACTOR;

  return (
    <group>
      <instancedMesh
        ref={bodyRef}
        args={[undefined, undefined, ovens.length]}
        castShadow
        receiveShadow
        onPointerMove={(e: ThreeEvent<PointerEvent>) => {
          e.stopPropagation();
          if (e.instanceId !== undefined && e.instanceId !== hoveredIndex) setHoveredIndex(e.instanceId);
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={(e: ThreeEvent<PointerEvent>) => {
          e.stopPropagation();
          setHoveredIndex(null);
          document.body.style.cursor = "auto";
        }}
        onClick={(e: ThreeEvent<MouseEvent>) => {
          e.stopPropagation();
          if (e.instanceId !== undefined) onSelect(ovens[e.instanceId].oven_id);
        }}
      >
        <boxGeometry args={[chamberWidth, CHAMBER_HEIGHT, CHAMBER_DEPTH]} />
        <meshStandardMaterial roughness={0.85} metalness={0.35} />
      </instancedMesh>

      {/* Status light housing — flush-mounted metal panel, same lit
          material family as the body. Carries no risk color itself. */}
      <instancedMesh ref={housingRef} args={[undefined, undefined, ovens.length]} castShadow receiveShadow>
        <boxGeometry args={[housingSize, HOUSING_HEIGHT, housingSize]} />
        <meshStandardMaterial color={HOUSING_COLOR} roughness={0.5} metalness={0.6} />
      </instancedMesh>

      {/* Status light lens — unlit so it reads as an always-on glow
          regardless of ambient/shadow darkening, recessed into the housing
          rather than the risk color painting the whole chamber. */}
      <instancedMesh ref={lensRef} args={[undefined, undefined, ovens.length]}>
        <boxGeometry args={[lensWidth, LENS_HEIGHT, lensDepth]} />
        <meshBasicMaterial toneMapped={false} />
      </instancedMesh>

      {selectedIndex >= 0 && (
        <mesh position={[ovens[selectedIndex].x, CHAMBER_HEIGHT / 2, ovens[selectedIndex].z]}>
          <boxGeometry args={[chamberWidth + 0.2, CHAMBER_HEIGHT + 0.3, CHAMBER_DEPTH + 0.3]} />
          <meshBasicMaterial transparent opacity={0} depthWrite={false} />
          <Edges color={SELECTION_COLOR} lineWidth={2.5} toneMapped={false} />
        </mesh>
      )}

      {labelOven && labelCategory !== null && (
        <Text
          position={[labelOven.x, CHAMBER_HEIGHT + 1.1, labelOven.z]}
          fontSize={0.9}
          color={colorForCategory(labelCategory)}
          anchorX="center"
          anchorY="middle"
          outlineWidth={0.04}
          outlineColor="#000000"
        >
          {`${labelOven.oven_id}  ${STATUS_GLYPH[RISK_CATEGORY_NAME[labelCategory]]}`}
        </Text>
      )}
    </group>
  );
}
