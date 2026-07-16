interface SceneDetailsProps {
  span: number;
  centerX: number;
  depth: number;
}

const CHIMNEY_HEIGHT = 26;

function Chimney({ x, z }: { x: number; z: number }) {
  return (
    <group position={[x, 0, z]}>
      <mesh position={[0, CHIMNEY_HEIGHT / 2, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[1.1, 1.6, CHIMNEY_HEIGHT, 16]} />
        <meshStandardMaterial color="#4a2f28" roughness={0.85} metalness={0.15} />
      </mesh>
      {/* warning band near the stack top */}
      <mesh position={[0, CHIMNEY_HEIGHT - 1.4, 0]} castShadow>
        <cylinderGeometry args={[1.16, 1.16, 2.0, 16]} />
        <meshStandardMaterial color="#d9d3c8" roughness={0.6} metalness={0.1} />
      </mesh>
    </group>
  );
}

function ServiceVehicle({ x, z }: { x: number; z: number }) {
  return (
    <group position={[x, 0, z]}>
      <mesh position={[0, 0.8, 0]} castShadow receiveShadow>
        <boxGeometry args={[4.2, 1.6, 1.9]} />
        <meshStandardMaterial color="#2c3440" roughness={0.5} metalness={0.4} />
      </mesh>
      <mesh position={[0, 1.75, -0.3]} castShadow>
        <boxGeometry args={[2.0, 0.9, 1.7]} />
        <meshStandardMaterial color="#1c2128" roughness={0.4} metalness={0.3} />
      </mesh>
    </group>
  );
}

/** Purely decorative scene dressing — chimney stacks for a strong vertical
 * landmark, plus a service vehicle near the battery base so the viewer's
 * eye has something familiar-sized to judge the structure's real scale
 * against. Human-scale figures now come from the real, data-driven
 * Workers.tsx instead of a hardcoded pair here. None of this is data-driven. */
export function SceneDetails({ span, centerX, depth }: SceneDetailsProps) {
  const startX = centerX - span / 2;
  const endX = centerX + span / 2;

  return (
    <group>
      <Chimney x={startX - 14} z={depth * 0.4} />
      <Chimney x={endX + 14} z={-depth * 0.4} />

      <ServiceVehicle x={startX + 42} z={depth / 2 + 6} />
    </group>
  );
}
