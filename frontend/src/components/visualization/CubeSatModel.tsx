/**
 * 6U CubeSat 3D model component.
 *
 * Dimensions: 10cm x 20cm x 30cm (1U = 10cm cube)
 */

import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import type { Group } from 'three';

interface CubeSatModelProps {
  quaternion: [number, number, number, number];
}

export function CubeSatModel({ quaternion }: CubeSatModelProps) {
  const groupRef = useRef<Group>(null);

  // Apply quaternion rotation each frame
  useFrame(() => {
    if (groupRef.current) {
      // Convert from [x, y, z, w] (scalar-last) to Three.js Quaternion
      const [x, y, z, w] = quaternion;
      groupRef.current.quaternion.set(x, y, z, w);
    }
  });

  // 6U CubeSat dimensions in meters (scaled up for visibility)
  const scale = 10; // Scale factor for visualization
  const width = 0.1 * scale;   // 10cm -> X axis
  const height = 0.2 * scale;  // 20cm -> Y axis
  const depth = 0.3 * scale;   // 30cm -> Z axis

  return (
    <group ref={groupRef}>
      {/* Main body */}
      <mesh>
        <boxGeometry args={[width, height, depth]} />
        <meshStandardMaterial color="#333" metalness={0.8} roughness={0.4} />
      </mesh>

      {/* Solar panels (deployed on +/- X faces) */}
      <SolarPanel position={[width / 2 + 0.4, 0, 0]} rotation={[0, 0, 0]} scale={scale} />
      <SolarPanel position={[-width / 2 - 0.4, 0, 0]} rotation={[0, 0, Math.PI]} scale={scale} />

      {/* Body frame axes indicator */}
      <BodyAxes scale={scale} />

      {/* Antenna */}
      <mesh position={[0, height / 2 + 0.15, 0]}>
        <cylinderGeometry args={[0.02, 0.02, 0.3]} />
        <meshStandardMaterial color="#888" metalness={0.9} roughness={0.2} />
      </mesh>
    </group>
  );
}

interface SolarPanelProps {
  position: [number, number, number];
  rotation: [number, number, number];
  scale: number;
}

function SolarPanel({ position, rotation, scale }: SolarPanelProps) {
  const panelWidth = 0.2 * scale;
  const panelHeight = 0.3 * scale;
  const panelThickness = 0.01 * scale;

  return (
    <group position={position} rotation={rotation}>
      {/* Panel frame */}
      <mesh>
        <boxGeometry args={[panelWidth, panelHeight, panelThickness]} />
        <meshStandardMaterial color="#1a237e" metalness={0.3} roughness={0.6} />
      </mesh>

      {/* Solar cells pattern */}
      <mesh position={[0, 0, panelThickness / 2 + 0.001]}>
        <planeGeometry args={[panelWidth * 0.9, panelHeight * 0.9]} />
        <meshStandardMaterial
          color="#0d47a1"
          metalness={0.5}
          roughness={0.3}
          emissive="#0d47a1"
          emissiveIntensity={0.1}
        />
      </mesh>
    </group>
  );
}

interface BodyAxesProps {
  scale: number;
}

function BodyAxes({ scale }: BodyAxesProps) {
  const axisLength = 0.5 * scale;
  const axisThickness = 0.02;

  return (
    <group>
      {/* X axis - Red */}
      <mesh position={[axisLength / 2, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[axisThickness, axisThickness, axisLength]} />
        <meshBasicMaterial color="#ff4444" />
      </mesh>
      <mesh position={[axisLength, 0, 0]}>
        <coneGeometry args={[axisThickness * 2, axisThickness * 6, 8]} />
        <meshBasicMaterial color="#ff4444" />
      </mesh>

      {/* Y axis - Green */}
      <mesh position={[0, axisLength / 2, 0]}>
        <cylinderGeometry args={[axisThickness, axisThickness, axisLength]} />
        <meshBasicMaterial color="#44ff44" />
      </mesh>
      <mesh position={[0, axisLength, 0]} rotation={[0, 0, 0]}>
        <coneGeometry args={[axisThickness * 2, axisThickness * 6, 8]} />
        <meshBasicMaterial color="#44ff44" />
      </mesh>

      {/* Z axis - Blue */}
      <mesh position={[0, 0, axisLength / 2]} rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[axisThickness, axisThickness, axisLength]} />
        <meshBasicMaterial color="#4444ff" />
      </mesh>
      <mesh position={[0, 0, axisLength]} rotation={[Math.PI / 2, 0, 0]}>
        <coneGeometry args={[axisThickness * 2, axisThickness * 6, 8]} />
        <meshBasicMaterial color="#4444ff" />
      </mesh>
    </group>
  );
}
