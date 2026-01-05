/**
 * 6U CubeSat 3D model component.
 *
 * Dimensions (1U = 10cm cube):
 *   X axis: 1U (10cm)
 *   Y axis: 2U (20cm)
 *   Z axis: 3U (30cm) - longest dimension
 *
 * Solar panels deployed from +Z end.
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
      {/* Main body - silver aluminum appearance */}
      <mesh>
        <boxGeometry args={[width, height, depth]} />
        <meshStandardMaterial color="#b8c4ce" metalness={0.8} roughness={0.2} />
      </mesh>

      {/* Solar panels (deployed from +Z end, parallel to +Z face, extending in ±X directions) */}
      {/* +X side panel */}
      <SolarPanel position={[width / 2 + 1.5, 0, depth / 2 + 0.05]} side="right" scale={scale} />
      {/* -X side panel */}
      <SolarPanel position={[-width / 2 - 1.5, 0, depth / 2 + 0.05]} side="left" scale={scale} />

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
  side: 'left' | 'right';
  scale: number;
}

function SolarPanel({ position, side: _side, scale }: SolarPanelProps) {
  // Panel size: 3U (X) x 2U (Y), parallel to +Z face
  const panelLength = 0.3 * scale;  // X direction (3U)
  const panelHeight = 0.2 * scale;  // Y direction (2U, same as body)
  const panelThickness = 0.01 * scale;

  return (
    <group position={position}>
      {/* Panel frame - lies in XY plane (parallel to +Z face) */}
      <mesh>
        <boxGeometry args={[panelLength, panelHeight, panelThickness]} />
        <meshStandardMaterial color="#1a237e" metalness={0.3} roughness={0.6} />
      </mesh>

      {/* Solar cells pattern - on +Z face */}
      <mesh position={[0, 0, panelThickness / 2 + 0.001]}>
        <planeGeometry args={[panelLength * 0.9, panelHeight * 0.9]} />
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
