/**
 * 3D Globe visualization using Three.js (react-three-fiber).
 *
 * Shows Earth with satellite orbit trajectory and current position.
 * Uses pure Three.js to avoid WebGPU compatibility issues with globe.gl.
 */

import { useRef, useMemo, useEffect } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { OrbitControls, Stars, PerspectiveCamera, Line } from '@react-three/drei';
import * as THREE from 'three';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import type { Telemetry } from '../../types/telemetry';
import type { OrbitHistoryPoint } from '../../hooks/useOrbitHistory';
import { CubeSatModel } from './CubeSatModel';
import { StatusOverlay } from '../StatusOverlay';

/** Camera offset in orbit frame (spherical coordinates) */
interface OrbitFrameOffset {
  /** Azimuth angle around zenith axis (radians) */
  theta: number;
  /** Elevation angle from orbit plane (radians) */
  phi: number;
  /** Distance from satellite */
  r: number;
}

type ViewCenter = 'earth' | 'satellite';

interface GlobeViewProps {
  telemetry: Telemetry | null;
  orbitHistory: OrbitHistoryPoint[];
  viewCenter: ViewCenter;
  onViewCenterChange: (center: ViewCenter) => void;
}

export function GlobeView({ telemetry, orbitHistory, viewCenter }: GlobeViewProps) {
  // Extract orbit data from telemetry
  const orbit = telemetry?.orbit;

  // Satellite position for camera target
  const satellitePosition = orbit?.positionThreeJS ?? [0, 0, 0];

  // Sun direction for day/night rendering
  const sunDirection = telemetry?.environment.sunDirection ?? [1, 0, 0];

  return (
    <div className="globe-view" style={{ width: '100%', height: '100%', background: '#000' }}>
      <Canvas>
        <PerspectiveCamera makeDefault position={[0, 0, 4]} fov={45} />
        <CameraController
          viewCenter={viewCenter}
          satellitePosition={satellitePosition as [number, number, number]}
          hasTelemetry={!!telemetry}
        />

        {/* Lighting - bright enough to see Earth and satellite from all angles */}
        <ambientLight intensity={0.5} />
        <directionalLight position={[5, 3, 5]} intensity={1.8} />
        <directionalLight position={[-5, -2, -5]} intensity={0.8} />
        <directionalLight position={[0, 5, -5]} intensity={0.6} />

        {/* Space background */}
        <Stars radius={100} depth={50} count={3000} factor={4} fade />

        {/* Earth with day/night shading */}
        <Earth sunDirection={sunDirection as [number, number, number]} />

        {/* Terminator line (day/night boundary) */}
        <Terminator sunDirection={sunDirection as [number, number, number]} />

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

      {/* Status overlay */}
      <StatusOverlay telemetry={telemetry} />

      {/* Orbit info overlay */}
      <OrbitOverlay telemetry={telemetry} />
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
  const { camera, gl } = useThree();

  // Camera offset in orbit frame (for satellite-following view)
  // theta: azimuth around zenith axis
  // phi: elevation from orbit plane (0 = in plane, positive = above)
  // r: distance from satellite
  const orbitOffset = useRef<OrbitFrameOffset>({
    theta: Math.PI / 4,   // 45° azimuth (behind and to the side)
    phi: Math.PI / 6,     // 30° elevation (slightly above orbit plane)
    r: 0.2                // distance from satellite
  });

  // Mouse drag state for satellite view
  const isDragging = useRef(false);
  const prevMouse = useRef({ x: 0, y: 0 });

  // Custom mouse handlers for satellite-following view
  useEffect(() => {
    if (viewCenter !== 'satellite') return;

    const canvas = gl.domElement;

    const onMouseDown = (e: MouseEvent) => {
      if (e.button === 0) { // Left click only
        isDragging.current = true;
        prevMouse.current = { x: e.clientX, y: e.clientY };
      }
    };

    const onMouseMove = (e: MouseEvent) => {
      if (!isDragging.current) return;

      const dx = e.clientX - prevMouse.current.x;
      const dy = e.clientY - prevMouse.current.y;
      prevMouse.current = { x: e.clientX, y: e.clientY };

      // Update orbit frame offset
      orbitOffset.current.theta += dx * 0.005;
      orbitOffset.current.phi = Math.max(
        -Math.PI / 2 + 0.1,
        Math.min(Math.PI / 2 - 0.1, orbitOffset.current.phi + dy * 0.005)
      );
    };

    const onMouseUp = () => {
      isDragging.current = false;
    };

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      orbitOffset.current.r = Math.max(
        0.03,
        Math.min(8, orbitOffset.current.r * (1 + e.deltaY * 0.001))
      );
    };

    canvas.addEventListener('mousedown', onMouseDown);
    canvas.addEventListener('mousemove', onMouseMove);
    canvas.addEventListener('mouseup', onMouseUp);
    canvas.addEventListener('mouseleave', onMouseUp);
    canvas.addEventListener('wheel', onWheel, { passive: false });

    return () => {
      canvas.removeEventListener('mousedown', onMouseDown);
      canvas.removeEventListener('mousemove', onMouseMove);
      canvas.removeEventListener('mouseup', onMouseUp);
      canvas.removeEventListener('mouseleave', onMouseUp);
      canvas.removeEventListener('wheel', onWheel);
    };
  }, [viewCenter, gl.domElement]);

  useFrame(() => {
    if (viewCenter === 'satellite' && hasTelemetry) {
      // Satellite-following camera in orbit frame (LVLH-like)
      const satPos = new THREE.Vector3(...satellitePosition);

      // Build orbit coordinate frame:
      // - Nadir: toward Earth center (down)
      // - Zenith: away from Earth (up)
      // - Tangent: perpendicular to nadir, roughly in orbit plane
      const nadir = satPos.clone().negate().normalize();
      const zenith = nadir.clone().negate();

      // Use scene Y (North pole) to define tangent direction
      const sceneUp = new THREE.Vector3(0, 1, 0);
      const tangent = new THREE.Vector3().crossVectors(sceneUp, nadir).normalize();

      // Handle polar case (nadir parallel to sceneUp)
      if (tangent.lengthSq() < 0.001) {
        tangent.set(1, 0, 0);
      }

      // Right vector (perpendicular to both tangent and zenith)
      const right = new THREE.Vector3().crossVectors(tangent, zenith).normalize();

      // Convert spherical offset to camera position in orbit frame
      const { theta, phi, r } = orbitOffset.current;
      const offset = new THREE.Vector3()
        .addScaledVector(tangent, r * Math.cos(phi) * Math.cos(theta))
        .addScaledVector(right, r * Math.cos(phi) * Math.sin(theta))
        .addScaledVector(zenith, r * Math.sin(phi));

      // Set camera position and orientation
      camera.position.copy(satPos).add(offset);
      camera.lookAt(satPos);
      camera.up.copy(zenith);

    } else if (controlsRef.current) {
      // Earth-centered view with OrbitControls
      controlsRef.current.target.lerp(new THREE.Vector3(0, 0, 0), 0.1);
      controlsRef.current.update();
    }
  });

  // Only enable OrbitControls for Earth view
  return (
    <OrbitControls
      ref={controlsRef}
      enabled={viewCenter === 'earth'}
      enablePan={false}
      enableZoom={true}
      enableRotate={true}
      minDistance={1.5}
      maxDistance={10}
      autoRotate={!hasTelemetry}
      autoRotateSpeed={0.5}
    />
  );
}

interface EarthProps {
  sunDirection: [number, number, number];
}

// Day/night shader for Earth
const earthVertexShader = `
  varying vec3 vNormalWorld;
  varying vec2 vUv;

  void main() {
    // Calculate normal in world space (not view space)
    // For a sphere at origin with no rotation, normal == position normalized
    // Using modelMatrix for correctness if Earth is ever transformed
    vNormalWorld = normalize((modelMatrix * vec4(normal, 0.0)).xyz);
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const earthFragmentShader = `
  uniform sampler2D dayTexture;
  uniform sampler2D nightTexture;
  uniform vec3 sunDirection;

  varying vec3 vNormalWorld;
  varying vec2 vUv;

  void main() {
    // Calculate sun illumination based on world-space surface normal and sun direction
    float sunDot = dot(normalize(vNormalWorld), normalize(sunDirection));

    // Smooth transition at terminator (twilight zone)
    // -0.15 to 0.15 creates a wider smooth blend region
    float dayFactor = smoothstep(-0.15, 0.15, sunDot);

    // Sample textures
    vec4 dayColor = texture2D(dayTexture, vUv);
    vec4 nightColor = texture2D(nightTexture, vUv);

    // Brighten night texture for better visibility
    vec4 brightNight = nightColor * 2.0 + vec4(0.02, 0.03, 0.05, 0.0);

    // Blend between day and night
    vec4 finalColor = mix(brightNight, dayColor, dayFactor);

    // Ensure night side has minimum visibility
    finalColor.rgb = max(finalColor.rgb, vec3(0.03, 0.04, 0.06));

    gl_FragColor = finalColor;
  }
`;

function Earth({ sunDirection }: EarthProps) {
  const meshRef = useRef<THREE.Mesh>(null);

  // Load day texture (NASA Blue Marble)
  const dayTexture = useMemo(() => {
    const loader = new THREE.TextureLoader();
    const tex = loader.load(
      'https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Land_ocean_ice_2048.jpg/2048px-Land_ocean_ice_2048.jpg',
      (loadedTex) => {
        loadedTex.colorSpace = THREE.SRGBColorSpace;
      }
    );
    tex.colorSpace = THREE.SRGBColorSpace;
    return tex;
  }, []);

  // Load night texture (Earth at night - city lights)
  const nightTexture = useMemo(() => {
    const loader = new THREE.TextureLoader();
    const tex = loader.load(
      'https://upload.wikimedia.org/wikipedia/commons/thumb/b/ba/The_earth_at_night.jpg/2048px-The_earth_at_night.jpg',
      (loadedTex) => {
        loadedTex.colorSpace = THREE.SRGBColorSpace;
      }
    );
    tex.colorSpace = THREE.SRGBColorSpace;
    return tex;
  }, []);

  // Create shader material with uniforms
  const shaderMaterial = useMemo(() => {
    return new THREE.ShaderMaterial({
      vertexShader: earthVertexShader,
      fragmentShader: earthFragmentShader,
      uniforms: {
        dayTexture: { value: dayTexture },
        nightTexture: { value: nightTexture },
        sunDirection: { value: new THREE.Vector3(1, 0, 0) },
      },
    });
  }, [dayTexture, nightTexture]);

  // Update sun direction uniform
  useFrame(() => {
    if (shaderMaterial.uniforms.sunDirection) {
      shaderMaterial.uniforms.sunDirection.value.set(...sunDirection);
    }
  });

  // Static Earth - no animation
  // Earth rotation is already accounted for in backend longitude calculation
  return (
    <mesh ref={meshRef} material={shaderMaterial}>
      <sphereGeometry args={[1, 64, 64]} />
    </mesh>
  );
}

interface TerminatorProps {
  sunDirection: [number, number, number];
}

function Terminator({ sunDirection }: TerminatorProps) {
  // Generate terminator circle points (great circle perpendicular to sun direction)
  const points = useMemo(() => {
    const sun = new THREE.Vector3(...sunDirection).normalize();

    // Find two vectors perpendicular to sun direction
    const up = new THREE.Vector3(0, 1, 0);
    let tangent = new THREE.Vector3().crossVectors(sun, up).normalize();

    // Handle case when sun is near poles
    if (tangent.lengthSq() < 0.001) {
      tangent = new THREE.Vector3(1, 0, 0);
    }

    const bitangent = new THREE.Vector3().crossVectors(sun, tangent).normalize();

    // Generate circle points on Earth surface (radius = 1.002 to be slightly above surface)
    const radius = 1.002;
    const segments = 128;
    const circlePoints: [number, number, number][] = [];

    for (let i = 0; i <= segments; i++) {
      const angle = (i / segments) * Math.PI * 2;
      const x = radius * (Math.cos(angle) * tangent.x + Math.sin(angle) * bitangent.x);
      const y = radius * (Math.cos(angle) * tangent.y + Math.sin(angle) * bitangent.y);
      const z = radius * (Math.cos(angle) * tangent.z + Math.sin(angle) * bitangent.z);
      circlePoints.push([x, y, z]);
    }

    return circlePoints;
  }, [sunDirection]);

  return (
    <Line
      points={points}
      color="#ff8800"
      lineWidth={2}
      transparent
      opacity={0.8}
    />
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

function OrbitOverlay({ telemetry }: Pick<OrbitOverlayProps, 'telemetry'>) {
  if (!telemetry || !telemetry.orbit) {
    return null;
  }

  const { latitude, longitude, altitude } = telemetry.orbit;

  return (
    <div className="orbit-overlay" style={{ top: '6rem' }}>
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
