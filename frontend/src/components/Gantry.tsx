import { useMemo } from "react";
import { CHAMBER_HEIGHT } from "./ovenGeometry";

interface GantryProps {
  span: number;
  centerX: number;
  depth: number; // zone/chamber footprint depth, so the rails track the wall's actual width
}

const RAIL_LIFT = 1.8; // rail deck height above the chamber roofline
const RAIL_HEIGHT = CHAMBER_HEIGHT + RAIL_LIFT;
const RAIL_THICKNESS = 0.5;
const COLUMN_SPACING_M = 15;
const STEEL = "#232320";

/** Charging-car rail gantry running the length of the battery — a distinct
 * darker steel framework above the oven roofline (support columns + cross
 * beams + the two rails themselves), purely structural dressing so the
 * battery reads as an industrial building, not a row of colored blocks. */
export function Gantry({ span, centerX, depth }: GantryProps) {
  const startX = centerX - span / 2;
  const endX = centerX + span / 2;
  const railZOffset = depth / 2 - 0.35;

  const columnXs = useMemo(() => {
    const xs: number[] = [];
    for (let x = startX + COLUMN_SPACING_M / 2; x < endX; x += COLUMN_SPACING_M) {
      xs.push(x);
    }
    return xs;
  }, [startX, endX]);

  return (
    <group>
      {[-1, 1].map((side) => (
        <mesh key={side} position={[centerX, RAIL_HEIGHT, side * railZOffset]} castShadow receiveShadow>
          <boxGeometry args={[span + 2, RAIL_THICKNESS, RAIL_THICKNESS * 1.4]} />
          <meshStandardMaterial color={STEEL} roughness={0.45} metalness={0.75} />
        </mesh>
      ))}

      {columnXs.map((x) => (
        <group key={x}>
          {[-1, 1].map((side) => (
            <mesh key={side} position={[x, CHAMBER_HEIGHT + RAIL_LIFT / 2, side * railZOffset]} castShadow>
              <boxGeometry args={[0.35, RAIL_LIFT, 0.35]} />
              <meshStandardMaterial color={STEEL} roughness={0.6} metalness={0.6} />
            </mesh>
          ))}
          <mesh position={[x, RAIL_HEIGHT, 0]} castShadow>
            <boxGeometry args={[0.3, 0.3, depth]} />
            <meshStandardMaterial color={STEEL} roughness={0.6} metalness={0.6} />
          </mesh>
        </group>
      ))}
    </group>
  );
}
