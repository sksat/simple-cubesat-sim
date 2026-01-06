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

interface GlobeViewProps {
  telemetry: Telemetry | null;
}

export function GlobeView({ telemetry }: GlobeViewProps) {
  // Extract orbit data from telemetry
  const orbit = telemetry?.orbit;

  // Default orbit parameters (600km SSO) used when no telemetry
  const orbitAltitude = orbit?.altitude ?? 600;
  const orbitInclination = orbit?.inclination ?? 97.8;

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

        {/* Satellite marker */}
        {orbit && (
          <SatelliteMarker
            latitude={orbit.latitude}
            longitude={orbit.longitude}
            altitude={orbit.altitude}
          />
        )}

        {/* Orbit path - uses parameters from telemetry */}
        <OrbitPath altitude={orbitAltitude} inclination={orbitInclination} />
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
}

function SatelliteMarker({ latitude, longitude, altitude }: SatelliteMarkerProps) {
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

  return (
    <group>
      {/* Satellite at orbital altitude */}
      <group position={[x, y, z]}>
        {/* Satellite body */}
        <mesh>
          <boxGeometry args={[0.03, 0.03, 0.05]} />
          <meshBasicMaterial color="#ff4444" />
        </mesh>
        {/* Glow effect */}
        <mesh>
          <sphereGeometry args={[0.06, 16, 16]} />
          <meshBasicMaterial color="#ff4444" transparent opacity={0.4} />
        </mesh>
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
        <sphereGeometry args={[0.02, 8, 8]} />
        <meshBasicMaterial color="#ffaa44" />
      </mesh>
    </group>
  );
}

interface OrbitPathProps {
  altitude: number;
  inclination: number;
}

function OrbitPath({ altitude, inclination }: OrbitPathProps) {
  const points = useMemo(() => {
    const earthRadius = 1;
    const altitudeScale = altitude / 6371;
    const r = earthRadius + altitudeScale;
    const incRad = (inclination * Math.PI) / 180;

    const pts: [number, number, number][] = [];
    for (let i = 0; i <= 360; i += 2) {
      const theta = (i * Math.PI) / 180;
      // Basic inclined circular orbit
      const x = r * Math.sin(theta);
      const y = r * Math.cos(theta) * Math.sin(incRad);
      const z = r * Math.cos(theta) * Math.cos(incRad);
      pts.push([x, y, z]);
    }
    return pts;
  }, [altitude, inclination]);

  return (
    <Line
      points={points}
      color="#4fc3f7"
      lineWidth={1}
      transparent
      opacity={0.6}
    />
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
