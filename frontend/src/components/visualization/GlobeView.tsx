/**
 * 3D Globe visualization using Three.js (react-three-fiber).
 *
 * Shows Earth with satellite orbit trajectory and current position.
 * Uses pure Three.js to avoid WebGPU compatibility issues with globe.gl.
 */

import { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Stars, PerspectiveCamera, Line } from '@react-three/drei';
import * as THREE from 'three';
import type { Telemetry } from '../../types/telemetry';
import type { OrbitHistoryPoint } from '../../hooks/useOrbitHistory';
import { CubeSatModel } from './CubeSatModel';

interface GlobeViewProps {
  telemetry: Telemetry | null;
  orbitHistory: OrbitHistoryPoint[];
}

export function GlobeView({ telemetry, orbitHistory }: GlobeViewProps) {
  // Extract orbit data from telemetry
  const orbit = telemetry?.orbit;

  return (
    <div className="globe-view" style={{ width: '100%', height: '100%', background: '#000' }}>
      <Canvas>
        <PerspectiveCamera makeDefault position={[0, 0, 4]} fov={45} />
        <OrbitControls
          enablePan={false}
          enableZoom={true}
          enableRotate={true}
          minDistance={1.5}
          maxDistance={10}
          autoRotate={!telemetry}
          autoRotateSpeed={0.5}
        />

        {/* Lighting */}
        <ambientLight intensity={0.3} />
        <directionalLight position={[5, 3, 5]} intensity={1.5} />

        {/* Space background */}
        <Stars radius={100} depth={50} count={3000} factor={4} fade />

        {/* Earth */}
        <Earth />

        {/* Satellite with CubeSat model */}
        {orbit && telemetry && (
          <SatelliteMarker
            latitude={orbit.latitude}
            longitude={orbit.longitude}
            altitude={orbit.altitude}
            quaternion={telemetry.attitude.quaternion}
          />
        )}

        {/* Ground track from orbit history */}
        <GroundTrack history={orbitHistory} />
      </Canvas>

      {/* Orbit info overlay */}
      <OrbitOverlay telemetry={telemetry} />
    </div>
  );
}

function Earth() {
  const meshRef = useRef<THREE.Mesh>(null);

  // Load NASA Blue Marble Earth texture
  const texture = useMemo(() => {
    const loader = new THREE.TextureLoader();
    // NASA Blue Marble texture (public domain)
    const tex = loader.load(
      'https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Land_ocean_ice_2048.jpg/2048px-Land_ocean_ice_2048.jpg',
      // On load callback
      (loadedTex) => {
        loadedTex.colorSpace = THREE.SRGBColorSpace;
      },
      // Progress callback
      undefined,
      // On error - fall back to procedural texture
      () => {
        console.warn('Failed to load Earth texture, using fallback');
      }
    );
    tex.colorSpace = THREE.SRGBColorSpace;
    return tex;
  }, []);

  // Slow rotation to simulate Earth rotation
  useFrame(() => {
    if (meshRef.current) {
      meshRef.current.rotation.y += 0.0005;
    }
  });

  return (
    <mesh ref={meshRef}>
      <sphereGeometry args={[1, 64, 64]} />
      <meshStandardMaterial
        map={texture}
        roughness={0.8}
        metalness={0.1}
      />
    </mesh>
  );
}

interface SatelliteMarkerProps {
  latitude: number;
  longitude: number;
  altitude: number;
  quaternion: [number, number, number, number];
}

function SatelliteMarker({ latitude, longitude, altitude, quaternion }: SatelliteMarkerProps) {
  const groupRef = useRef<THREE.Group>(null);

  // Convert lat/lon/alt to 3D position
  // Earth radius = 1, altitude in km scaled to scene
  const earthRadius = 1;
  const altitudeScale = altitude / 6371; // Earth radius = 6371 km
  const r = earthRadius + altitudeScale;

  const latRad = (latitude * Math.PI) / 180;
  const lonRad = (longitude * Math.PI) / 180;

  const x = r * Math.cos(latRad) * Math.sin(lonRad);
  const y = r * Math.sin(latRad);
  const z = r * Math.cos(latRad) * Math.cos(lonRad);

  // Ground position (on Earth surface)
  const groundX = earthRadius * Math.cos(latRad) * Math.sin(lonRad);
  const groundY = earthRadius * Math.sin(latRad);
  const groundZ = earthRadius * Math.cos(latRad) * Math.cos(lonRad);

  // Compute local frame transformation
  // The satellite's local "up" should point radially outward
  // We need to rotate from inertial frame (Z-up) to local frame (radial-up)
  const localFrameQuaternion = useMemo(() => {
    // Radial direction (local up)
    const radial = new THREE.Vector3(x, y, z).normalize();

    // We want to find the rotation that transforms (0, 0, 1) to radial
    // Using quaternion from rotation axis and angle
    const inertialUp = new THREE.Vector3(0, 0, 1);

    const q = new THREE.Quaternion();
    q.setFromUnitVectors(inertialUp, radial);

    return q;
  }, [x, y, z]);

  // Apply combined rotation: local frame + attitude
  useFrame(() => {
    if (groupRef.current) {
      // Attitude quaternion from telemetry
      const attitudeQ = new THREE.Quaternion(quaternion[0], quaternion[1], quaternion[2], quaternion[3]);

      // Combined: first local frame rotation, then attitude
      // Final = localFrame * attitude
      const combined = localFrameQuaternion.clone().multiply(attitudeQ);

      groupRef.current.quaternion.copy(combined);
    }
  });

  // Scale factor for the satellite model in globe view (much smaller than attitude view)
  const satelliteScale = 0.008;

  return (
    <group>
      {/* Satellite at orbital altitude with CubeSat model */}
      <group position={[x, y, z]} ref={groupRef}>
        <group scale={[satelliteScale, satelliteScale, satelliteScale]}>
          <CubeSatModel quaternion={[0, 0, 0, 1]} />
        </group>
      </group>
      {/* Ground track line from satellite to Earth surface */}
      <Line
        points={[[x, y, z], [groundX, groundY, groundZ]]}
        color="#ff4444"
        lineWidth={1}
        transparent
        opacity={0.5}
      />
      {/* Ground marker */}
      <mesh position={[groundX, groundY, groundZ]}>
        <sphereGeometry args={[0.015, 8, 8]} />
        <meshBasicMaterial color="#ffaa44" />
      </mesh>
    </group>
  );
}

interface GroundTrackProps {
  history: OrbitHistoryPoint[];
}

function GroundTrack({ history }: GroundTrackProps) {
  // Convert orbit history to 3D points
  // Need to handle longitude discontinuities (wrap-around at ±180°)
  const segments = useMemo(() => {
    if (history.length < 2) return [];

    const earthRadius = 1;
    const allSegments: [number, number, number][][] = [];
    let currentSegment: [number, number, number][] = [];

    for (let i = 0; i < history.length; i++) {
      const point = history[i];
      const altitudeScale = point.altitude / 6371;
      const r = earthRadius + altitudeScale;

      const latRad = (point.latitude * Math.PI) / 180;
      const lonRad = (point.longitude * Math.PI) / 180;

      const x = r * Math.cos(latRad) * Math.sin(lonRad);
      const y = r * Math.sin(latRad);
      const z = r * Math.cos(latRad) * Math.cos(lonRad);

      // Check for longitude discontinuity (wrap-around)
      if (i > 0) {
        const prevLon = history[i - 1].longitude;
        const currLon = point.longitude;
        // If longitude jumps by more than 180°, start a new segment
        if (Math.abs(currLon - prevLon) > 180) {
          if (currentSegment.length >= 2) {
            allSegments.push(currentSegment);
          }
          currentSegment = [];
        }
      }

      currentSegment.push([x, y, z]);
    }

    // Add final segment
    if (currentSegment.length >= 2) {
      allSegments.push(currentSegment);
    }

    return allSegments;
  }, [history]);

  if (segments.length === 0) return null;

  return (
    <group>
      {segments.map((segment, i) => (
        <Line
          key={i}
          points={segment}
          color="#4fc3f7"
          lineWidth={2}
          transparent
          opacity={0.7}
        />
      ))}
    </group>
  );
}

interface OrbitOverlayProps {
  telemetry: Telemetry | null;
}

function OrbitOverlay({ telemetry }: OrbitOverlayProps) {
  if (!telemetry || !telemetry.orbit) {
    return (
      <div className="orbit-overlay">
        <span>No telemetry</span>
      </div>
    );
  }

  const { latitude, longitude, altitude } = telemetry.orbit;

  return (
    <div className="orbit-overlay">
      <div className="orbit-position">
        <span>Lat: {latitude.toFixed(2)}°</span>
        <span>Lon: {longitude.toFixed(2)}°</span>
        <span>Alt: {altitude.toFixed(1)} km</span>
      </div>
      <div className="orbit-time">
        <span>Time: {telemetry.timestamp.toFixed(1)}s</span>
      </div>
    </div>
  );
}
