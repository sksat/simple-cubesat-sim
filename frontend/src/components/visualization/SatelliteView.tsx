/**
 * 3D Satellite visualization using Three.js (react-three-fiber).
 *
 * Shows the CubeSat with real-time attitude from telemetry.
 */

import { Canvas } from '@react-three/fiber';
import { OrbitControls, Grid, Stars, PerspectiveCamera } from '@react-three/drei';
import { CubeSatModel } from './CubeSatModel';
import type { Telemetry } from '../../types/telemetry';

interface SatelliteViewProps {
  telemetry: Telemetry | null;
}

export function SatelliteView({ telemetry }: SatelliteViewProps) {
  // Default quaternion (identity - no rotation)
  const quaternion: [number, number, number, number] = telemetry?.attitude.quaternion ?? [0, 0, 0, 1];

  return (
    <div style={{ width: '100%', height: '100%', background: '#0a0a1a' }}>
      <Canvas>
        <PerspectiveCamera makeDefault position={[8, 6, 8]} fov={50} />
        <OrbitControls
          enablePan={true}
          enableZoom={true}
          enableRotate={true}
          minDistance={3}
          maxDistance={30}
        />

        {/* Lighting */}
        <ambientLight intensity={0.3} />
        <directionalLight
          position={[10, 10, 5]}
          intensity={1.5}
          castShadow
        />
        <directionalLight
          position={[-5, -5, -5]}
          intensity={0.3}
        />

        {/* Space background */}
        <Stars radius={100} depth={50} count={2000} factor={4} fade />

        {/* Reference grid (inertial frame) */}
        <Grid
          infiniteGrid
          cellSize={1}
          cellThickness={0.5}
          cellColor="#333"
          sectionSize={5}
          sectionThickness={1}
          sectionColor="#555"
          fadeDistance={50}
          fadeStrength={1}
        />

        {/* Inertial frame axes */}
        <InertialAxes />

        {/* CubeSat model */}
        <CubeSatModel quaternion={quaternion} />
      </Canvas>

      {/* Attitude overlay info */}
      <AttitudeOverlay telemetry={telemetry} />
    </div>
  );
}

function InertialAxes() {
  const length = 8;
  const thickness = 0.03;

  return (
    <group>
      {/* X axis - Red (dashed line style) */}
      <mesh position={[length / 2, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[thickness, thickness, length]} />
        <meshBasicMaterial color="#ff0000" opacity={0.4} transparent />
      </mesh>

      {/* Y axis - Green */}
      <mesh position={[0, length / 2, 0]}>
        <cylinderGeometry args={[thickness, thickness, length]} />
        <meshBasicMaterial color="#00ff00" opacity={0.4} transparent />
      </mesh>

      {/* Z axis - Blue */}
      <mesh position={[0, 0, length / 2]} rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[thickness, thickness, length]} />
        <meshBasicMaterial color="#0000ff" opacity={0.4} transparent />
      </mesh>

      {/* Axis labels */}
      <AxisLabel text="X" position={[length + 0.5, 0, 0]} color="#ff0000" />
      <AxisLabel text="Y" position={[0, length + 0.5, 0]} color="#00ff00" />
      <AxisLabel text="Z" position={[0, 0, length + 0.5]} color="#0000ff" />
    </group>
  );
}

interface AxisLabelProps {
  text: string;
  position: [number, number, number];
  color: string;
}

function AxisLabel({ text: _text, position, color }: AxisLabelProps) {
  // Simple sphere marker for axis end
  // TODO: Use @react-three/drei Text component for proper labels
  return (
    <mesh position={position}>
      <sphereGeometry args={[0.15]} />
      <meshBasicMaterial color={color} />
    </mesh>
  );
}

interface AttitudeOverlayProps {
  telemetry: Telemetry | null;
}

function AttitudeOverlay({ telemetry }: AttitudeOverlayProps) {
  if (!telemetry) {
    return (
      <div className="attitude-overlay">
        <span>No telemetry</span>
      </div>
    );
  }

  const euler = telemetry.attitude.eulerAngles;
  const omega = telemetry.attitude.angularVelocity;
  const omegaDeg = omega.map(w => (w * 180 / Math.PI).toFixed(1));

  return (
    <div className="attitude-overlay">
      <div className="attitude-euler">
        <span>Roll: {euler[0].toFixed(1)}°</span>
        <span>Pitch: {euler[1].toFixed(1)}°</span>
        <span>Yaw: {euler[2].toFixed(1)}°</span>
      </div>
      <div className="attitude-rate">
        <span>ω: [{omegaDeg.join(', ')}] °/s</span>
      </div>
    </div>
  );
}
