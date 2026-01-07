/**
 * Ground station marker with visibility footprint circle.
 *
 * Renders a green marker on Earth surface and a circle showing
 * the visibility footprint where satellite can be seen.
 */

import { useMemo } from 'react';
import { Line } from '@react-three/drei';
import * as THREE from 'three';
import type { GroundStationState } from '../../types/telemetry';

interface GroundStationMarkerProps {
  station: GroundStationState;
}

export function GroundStationMarker({ station }: GroundStationMarkerProps) {
  const { positionThreeJS, footprintRadius, isVisible } = station;
  const [x, y, z] = positionThreeJS;

  // Generate footprint circle points on Earth surface
  const footprintPoints = useMemo(() => {
    // Ground station position as a unit vector (Earth center to station)
    const gsPos = new THREE.Vector3(x, y, z).normalize();

    // Find two perpendicular vectors on the tangent plane
    const up = new THREE.Vector3(0, 1, 0);
    const tangentRaw = new THREE.Vector3().crossVectors(up, gsPos);

    // Handle case when station is near poles
    const tangent = tangentRaw.lengthSq() < 0.001
      ? new THREE.Vector3(1, 0, 0)
      : tangentRaw.normalize();

    const bitangent = new THREE.Vector3().crossVectors(gsPos, tangent).normalize();

    // Convert footprint radius to radians
    const radiusRad = (footprintRadius * Math.PI) / 180;

    // Generate circle points
    // The circle is on Earth surface at angle = footprintRadius from ground station
    const segments = 64;
    const points: [number, number, number][] = [];
    const earthRadius = 1.002; // Slightly above surface to avoid z-fighting

    for (let i = 0; i <= segments; i++) {
      const angle = (i / segments) * Math.PI * 2;

      // Point on unit sphere at angular distance radiusRad from gsPos
      // Using spherical geometry: rotate gsPos by radiusRad toward tangent/bitangent direction
      const cosR = Math.cos(radiusRad);
      const sinR = Math.sin(radiusRad);

      // Direction on the circle (combination of tangent and bitangent)
      const circleDir = new THREE.Vector3()
        .addScaledVector(tangent, Math.cos(angle))
        .addScaledVector(bitangent, Math.sin(angle));

      // Point on sphere: rotate gsPos toward circleDir by radiusRad
      const point = new THREE.Vector3()
        .addScaledVector(gsPos, cosR)
        .addScaledVector(circleDir, sinR)
        .normalize()
        .multiplyScalar(earthRadius);

      points.push([point.x, point.y, point.z]);
    }

    return points;
  }, [x, y, z, footprintRadius]);

  // Color based on visibility status
  const markerColor = isVisible ? '#00ff00' : '#008800';
  const footprintColor = isVisible ? '#00ff00' : '#006600';

  // Position marker slightly above surface
  const markerRadius = 1.003;
  const markerPos = new THREE.Vector3(x, y, z).normalize().multiplyScalar(markerRadius);

  return (
    <group>
      {/* Ground station marker */}
      <mesh position={[markerPos.x, markerPos.y, markerPos.z]}>
        <sphereGeometry args={[0.02, 16, 16]} />
        <meshBasicMaterial color={markerColor} />
      </mesh>

      {/* Visibility footprint circle */}
      <Line
        points={footprintPoints}
        color={footprintColor}
        lineWidth={2}
        transparent
        opacity={isVisible ? 0.8 : 0.4}
      />
    </group>
  );
}
