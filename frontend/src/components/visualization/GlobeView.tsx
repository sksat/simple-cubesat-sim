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
  const orbitData = telemetry ? {
    latitude: telemetry.orbit?.latitude ?? 0,
    longitude: telemetry.orbit?.longitude ?? 0,
    altitude: telemetry.orbit?.altitude ?? 400,
  } : null;

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
        {orbitData && (
          <SatelliteMarker
            latitude={orbitData.latitude}
            longitude={orbitData.longitude}
            altitude={orbitData.altitude}
          />
        )}

        {/* Orbit path */}
        <OrbitPath altitude={400} inclination={51.6} />
      </Canvas>

      {/* Orbit info overlay */}
      <OrbitOverlay telemetry={telemetry} />
    </div>
  );
}

function Earth() {
  const meshRef = useRef<THREE.Mesh>(null);

  // Create procedural Earth texture (simple color gradient)
  const texture = useMemo(() => {
    const canvas = document.createElement('canvas');
    canvas.width = 512;
    canvas.height = 256;
    const ctx = canvas.getContext('2d')!;

    // Ocean base
    ctx.fillStyle = '#1a3a5c';
    ctx.fillRect(0, 0, 512, 256);

    // Simple continent shapes (very basic)
    ctx.fillStyle = '#2d5a3d';

    // North America
    ctx.beginPath();
    ctx.ellipse(100, 80, 50, 40, 0, 0, Math.PI * 2);
    ctx.fill();

    // South America
    ctx.beginPath();
    ctx.ellipse(130, 160, 25, 50, 0.3, 0, Math.PI * 2);
    ctx.fill();

    // Europe/Africa
    ctx.beginPath();
    ctx.ellipse(260, 100, 30, 60, 0, 0, Math.PI * 2);
    ctx.fill();

    // Asia
    ctx.beginPath();
    ctx.ellipse(360, 80, 70, 50, 0, 0, Math.PI * 2);
    ctx.fill();

    // Australia
    ctx.beginPath();
    ctx.ellipse(420, 170, 25, 20, 0, 0, Math.PI * 2);
    ctx.fill();

    // Ice caps
    ctx.fillStyle = '#cce5ff';
    ctx.fillRect(0, 0, 512, 15);
    ctx.fillRect(0, 241, 512, 15);

    const tex = new THREE.CanvasTexture(canvas);
    tex.needsUpdate = true;
    return tex;
  }, []);

  // Slow rotation
  useFrame(() => {
    if (meshRef.current) {
      meshRef.current.rotation.y += 0.001;
    }
  });

  return (
    <mesh ref={meshRef}>
      <sphereGeometry args={[1, 64, 32]} />
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

  return (
    <group position={[x, y, z]}>
      {/* Satellite body */}
      <mesh>
        <boxGeometry args={[0.02, 0.02, 0.03]} />
        <meshBasicMaterial color="#ff4444" />
      </mesh>
      {/* Glow effect */}
      <mesh>
        <sphereGeometry args={[0.04, 16, 16]} />
        <meshBasicMaterial color="#ff4444" transparent opacity={0.3} />
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
