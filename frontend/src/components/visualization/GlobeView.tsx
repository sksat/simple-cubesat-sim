/**
 * 3D Globe visualization using Three.js (react-three-fiber).
 *
 * Shows Earth with satellite orbit trajectory and current position.
 * Uses pure Three.js to avoid WebGPU compatibility issues with globe.gl.
 */

import { useRef, useMemo, useState } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { OrbitControls, Stars, PerspectiveCamera, Line } from '@react-three/drei';
import * as THREE from 'three';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import type { Telemetry } from '../../types/telemetry';
import type { OrbitHistoryPoint } from '../../hooks/useOrbitHistory';
import { CubeSatModel } from './CubeSatModel';

type ViewCenter = 'earth' | 'satellite';

interface GlobeViewProps {
  telemetry: Telemetry | null;
  orbitHistory: OrbitHistoryPoint[];
}

export function GlobeView({ telemetry, orbitHistory }: GlobeViewProps) {
  // Extract orbit data from telemetry
  const orbit = telemetry?.orbit;
  const [viewCenter, setViewCenter] = useState<ViewCenter>('satellite');

  // Satellite position for camera target
  const satellitePosition = orbit?.positionThreeJS ?? [0, 0, 0];

  return (
    <div className="globe-view" style={{ width: '100%', height: '100%', background: '#000' }}>
      <Canvas>
        <PerspectiveCamera makeDefault position={[0, 0, 4]} fov={45} />
        <CameraController
          viewCenter={viewCenter}
          satellitePosition={satellitePosition as [number, number, number]}
          hasTelemetry={!!telemetry}
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
            position={orbit.positionThreeJS}
            quaternion={telemetry.attitude.quaternion}
          />
        )}

        {/* Ground track from orbit history */}
        <GroundTrack history={orbitHistory} />
      </Canvas>

      {/* Orbit info overlay */}
      <OrbitOverlay
        telemetry={telemetry}
        viewCenter={viewCenter}
        onViewCenterChange={setViewCenter}
      />
    </div>
  );
}

interface CameraControllerProps {
  viewCenter: ViewCenter;
  satellitePosition: [number, number, number];
  hasTelemetry: boolean;
}

function CameraController({ viewCenter, satellitePosition, hasTelemetry }: CameraControllerProps) {
  const controlsRef = useRef<OrbitControlsImpl>(null);
  const { camera } = useThree();

  // Update camera target based on view center
  useFrame(() => {
    if (!controlsRef.current) return;

    const controls = controlsRef.current;

    if (viewCenter === 'satellite' && hasTelemetry) {
      // Smoothly interpolate target to satellite position
      const targetPos = new THREE.Vector3(...satellitePosition);
      controls.target.lerp(targetPos, 0.1);

      // Adjust camera to maintain relative distance from satellite
      const currentDistance = camera.position.distanceTo(controls.target);
      if (currentDistance > 0.5) {
        // Gradually zoom in when switching to satellite view
        const direction = camera.position.clone().sub(controls.target).normalize();
        const targetDistance = Math.max(0.15, currentDistance * 0.98);
        camera.position.copy(controls.target).add(direction.multiplyScalar(targetDistance));
      }
    } else {
      // Smoothly return to Earth center
      controls.target.lerp(new THREE.Vector3(0, 0, 0), 0.1);
    }

    controls.update();
  });

  // Dynamic distance limits based on view center
  const minDistance = viewCenter === 'satellite' ? 0.05 : 1.5;
  const maxDistance = viewCenter === 'satellite' ? 2 : 10;

  return (
    <OrbitControls
      ref={controlsRef}
      enablePan={false}
      enableZoom={true}
      enableRotate={true}
      minDistance={minDistance}
      maxDistance={maxDistance}
      autoRotate={!hasTelemetry && viewCenter === 'earth'}
      autoRotateSpeed={0.5}
    />
  );
}

function Earth() {
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

  // Static Earth - no animation
  // Earth rotation is already accounted for in backend longitude calculation
  // Backend coordinate system (Astropy ECEF → Three.js):
  //   Scene X: lon=0° (prime meridian)
  //   Scene Y: North Pole (up)
  //   Scene Z: lon=90°E
  // Three.js SphereGeometry maps texture center (u=0.5, lon=0) to +X, which matches.
  return (
    <mesh>
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
  /** Pre-computed Three.js position from backend (Astropy) */
  position: [number, number, number];
  quaternion: [number, number, number, number];
}

function SatelliteMarker({ position, quaternion }: SatelliteMarkerProps) {
  const groupRef = useRef<THREE.Group>(null);

  // Position from backend (already in Three.js coordinates via Astropy)
  const [x, y, z] = position;

  // Ground position (normalized to Earth surface, radius = 1)
  const r = Math.sqrt(x * x + y * y + z * z);
  const groundX = x / r;
  const groundY = y / r;
  const groundZ = z / r;

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
  // Use pre-computed Three.js coordinates from backend (Astropy)
  // Handle longitude discontinuities (wrap-around at ±180°) for line segments
  const segments = useMemo(() => {
    if (history.length < 2) return [];

    const allSegments: [number, number, number][][] = [];
    let currentSegment: [number, number, number][] = [];

    for (let i = 0; i < history.length; i++) {
      const point = history[i];

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

      // Use pre-computed position from backend
      currentSegment.push(point.positionThreeJS);
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
  viewCenter: ViewCenter;
  onViewCenterChange: (center: ViewCenter) => void;
}

function OrbitOverlay({ telemetry, viewCenter, onViewCenterChange }: OrbitOverlayProps) {
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
      <div className="view-center-toggle">
        <button
          className={viewCenter === 'earth' ? 'active' : ''}
          onClick={() => onViewCenterChange('earth')}
        >
          Earth
        </button>
        <button
          className={viewCenter === 'satellite' ? 'active' : ''}
          onClick={() => onViewCenterChange('satellite')}
        >
          Satellite
        </button>
      </div>
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
