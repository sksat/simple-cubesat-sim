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
import * as THREE from 'three';
import type { Group } from 'three';

interface CubeSatModelProps {
  quaternion: [number, number, number, number];
  sunDirection?: [number, number, number] | null;
  /** If true, don't apply rotation to groupRef (used when parent already applies rotation) */
  disableRotation?: boolean;
}

export function CubeSatModel({ quaternion, sunDirection, disableRotation = false }: CubeSatModelProps) {
  const groupRef = useRef<Group>(null);

  // Apply quaternion rotation each frame (unless disabled)
  useFrame(() => {
    if (groupRef.current && !disableRotation) {
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

  // Sun direction transformation for body frame display:
  // sunDirection comes in ECI (inertial) frame, so we can use inverse quaternion to transform to body frame
  // But we want to display it fixed in inertial frame, so we apply qInv to cancel spacecraft rotation
  const qInv = new THREE.Quaternion(quaternion[0], quaternion[1], quaternion[2], quaternion[3]).invert();

  return (
    <group ref={groupRef}>
      {/* Main body - silver aluminum appearance */}
      <mesh>
        <boxGeometry args={[width, height, depth]} />
        <meshStandardMaterial color="#b8c4ce" metalness={0.8} roughness={0.2} />
      </mesh>

      {/* Solar panels (deployed from +Z end, parallel to +Z face, extending in ±X directions) */}
      {/* +X side panel */}
      <SolarPanel position={[width / 2 + 1.5, 0, depth / 2 + 0.05]} scale={scale} />
      {/* -X side panel */}
      <SolarPanel position={[-width / 2 - 1.5, 0, depth / 2 + 0.05]} scale={scale} />

      {/* Body frame axes indicator */}
      <BodyAxes scale={scale} />

      {/* Sun direction arrow in inertial frame (fixed to sun direction) */}
      {sunDirection && (
        <InertialSunArrow sunDirection={sunDirection} qInv={qInv} scale={scale} />
      )}

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
  scale: number;
}

function SolarPanel({ position, scale }: SolarPanelProps) {
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

interface InertialSunArrowProps {
  sunDirection: [number, number, number];
  qInv: THREE.Quaternion;
  scale: number;
}

/**
 * Sun direction arrow that stays fixed in inertial frame.
 * Uses inverse quaternion to cancel out spacecraft rotation.
 */
function InertialSunArrow({ sunDirection, qInv, scale }: InertialSunArrowProps) {
  const [x, y, z] = sunDirection;
  const axisLength = 0.3 * scale;  // Shorter for better visibility
  const axisThickness = 0.05;  // Thicker for emphasis

  // Calculate magnitude
  const magnitude = Math.sqrt(x * x + y * y + z * z);
  if (magnitude < 0.001) return null;

  // Normalize direction
  const nx = x / magnitude;
  const ny = y / magnitude;
  const nz = z / magnitude;

  // Calculate rotation to orient arrow towards sun
  const sunVec = new THREE.Vector3(nx, ny, nz);
  const upVec = new THREE.Vector3(0, 1, 0);
  const axis = new THREE.Vector3().crossVectors(upVec, sunVec).normalize();
  const angle = Math.acos(upVec.dot(sunVec));

  const arrowRotation = new THREE.Quaternion();
  if (axis.length() > 0.001) {
    arrowRotation.setFromAxisAngle(axis, angle);
  }

  // Combine inverse spacecraft rotation with arrow rotation
  // This keeps arrow pointing at sun in inertial frame
  const finalRotation = qInv.clone().multiply(arrowRotation);

  return (
    <group quaternion={finalRotation}>
      {/* Arrow shaft */}
      <mesh position={[0, axisLength / 2, 0]}>
        <cylinderGeometry args={[axisThickness, axisThickness, axisLength]} />
        <meshStandardMaterial
          color="#ffa500"
          emissive="#ffa500"
          emissiveIntensity={0.8}
        />
      </mesh>
      {/* Arrow head */}
      <mesh position={[0, axisLength, 0]}>
        <coneGeometry args={[axisThickness * 2, axisThickness * 6, 8]} />
        <meshStandardMaterial
          color="#ffa500"
          emissive="#ffa500"
          emissiveIntensity={0.8}
        />
      </mesh>
      {/* Sun marker at the tip */}
      <group position={[0, axisLength + axisThickness * 8, 0]}>
        {/* Central sun sphere */}
        <mesh>
          <sphereGeometry args={[axisThickness * 3, 16, 16]} />
          <meshStandardMaterial
            color="#ffee88"
            emissive="#ffdd00"
            emissiveIntensity={0.8}
          />
        </mesh>
        {/* Sun rays (8 directions) */}
        {Array.from({ length: 8 }).map((_, i) => {
          const angle = (i * Math.PI) / 4;
          return (
            <mesh key={i} rotation={[0, 0, angle]}>
              <planeGeometry args={[axisThickness * 0.8, axisThickness * 6]} />
              <meshStandardMaterial
                color="#ffcc00"
                emissive="#ff9900"
                emissiveIntensity={0.5}
                transparent
                opacity={0.4}
                side={THREE.DoubleSide}
              />
            </mesh>
          );
        })}
      </group>
    </group>
  );
}

export interface SunDirectionArrowProps {
  sunDirection: [number, number, number];
  /** Arrow length (defaults to 5.0) */
  length?: number;
}

/**
 * Sun direction arrow indicator.
 * Displays an orange arrow pointing towards the sun direction.
 * The arrow is placed in scene coordinates (not body frame).
 */
export function SunDirectionArrow({ sunDirection, length = 5.0 }: SunDirectionArrowProps) {
  const [x, y, z] = sunDirection;

  const arrowLength = length;
  const arrowThickness = 0.05;  // Thicker for emphasis
  const coneHeight = arrowThickness * 6;
  const coneRadius = arrowThickness * 2;

  // Calculate magnitude
  const magnitude = Math.sqrt(x * x + y * y + z * z);
  if (magnitude < 0.001) return null; // Skip if sun direction is invalid

  // Normalize sun direction
  const nx = x / magnitude;
  const ny = y / magnitude;
  const nz = z / magnitude;

  // Calculate rotation to orient arrow towards sun
  // We need to rotate from default Y-axis (0,1,0) to sun direction (nx,ny,nz)

  // Create quaternion for rotation
  // Using lookAt approach: calculate rotation to point Y-axis towards sun
  const sunVec = new THREE.Vector3(nx, ny, nz);
  const upVec = new THREE.Vector3(0, 1, 0);

  // Calculate rotation axis (cross product of up and sun direction)
  const axis = new THREE.Vector3().crossVectors(upVec, sunVec).normalize();

  // Calculate rotation angle
  const angle = Math.acos(upVec.dot(sunVec));

  // Create quaternion
  const quaternion = new THREE.Quaternion();
  if (axis.length() > 0.001) {
    quaternion.setFromAxisAngle(axis, angle);
  }

  return (
    <group quaternion={quaternion}>
      {/* Arrow shaft - positioned along Y axis from origin */}
      <mesh position={[0, arrowLength / 2, 0]}>
        <cylinderGeometry args={[arrowThickness, arrowThickness, arrowLength]} />
        <meshStandardMaterial
          color="#ffa500"
          emissive="#ffa500"
          emissiveIntensity={0.8}
        />
      </mesh>

      {/* Arrow head (cone) - positioned at end of shaft */}
      <mesh position={[0, arrowLength + coneHeight / 2, 0]}>
        <coneGeometry args={[coneRadius, coneHeight, 8]} />
        <meshStandardMaterial
          color="#ffa500"
          emissive="#ffa500"
          emissiveIntensity={0.8}
        />
      </mesh>

      {/* Sun marker at the tip */}
      <group position={[0, arrowLength + coneHeight + arrowThickness * 2, 0]}>
        {/* Central sun sphere */}
        <mesh>
          <sphereGeometry args={[arrowThickness * 3, 16, 16]} />
          <meshStandardMaterial
            color="#ffee88"
            emissive="#ffdd00"
            emissiveIntensity={0.8}
          />
        </mesh>
        {/* Sun rays (8 directions) */}
        {Array.from({ length: 8 }).map((_, i) => {
          const angle = (i * Math.PI) / 4;
          return (
            <mesh key={i} rotation={[0, 0, angle]}>
              <planeGeometry args={[arrowThickness * 0.8, arrowThickness * 6]} />
              <meshStandardMaterial
                color="#ffcc00"
                emissive="#ff9900"
                emissiveIntensity={0.5}
                transparent
                opacity={0.4}
                side={THREE.DoubleSide}
              />
            </mesh>
          );
        })}
      </group>
    </group>
  );
}
