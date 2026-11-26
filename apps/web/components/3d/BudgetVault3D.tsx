"use client";

import { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { WebGLGuard, useReducedMotion } from "./WebGLGuard";

function VaultDial({
  remainingRatio,
  paused,
  reduced,
}: {
  remainingRatio: number;
  paused: boolean;
  reduced: boolean;
}) {
  const groupRef = useRef<THREE.Group>(null);
  const sealRef = useRef<THREE.Mesh>(null);
  const arcAngle = Math.max(0.08, Math.min(1, remainingRatio)) * Math.PI * 2;
  const ticks = useMemo(() => Array.from({ length: 12 }, (_, i) => (i / 12) * Math.PI * 2), []);

  const ringColor = paused ? "#c8452b" : remainingRatio > 0.35 ? "#3f6b4f" : "#c89a4b";

  useFrame(({ clock }) => {
    if (reduced) return;
    const t = clock.getElapsedTime();
    if (groupRef.current) {
      groupRef.current.rotation.y = Math.sin(t * 0.4) * 0.18;
    }
    if (sealRef.current && !paused) {
      sealRef.current.rotation.y = t * 0.55;
      sealRef.current.rotation.z = Math.sin(t * 0.8) * 0.1;
    }
  });

  return (
    <>
      <ambientLight intensity={0.65} />
      <directionalLight position={[4, 5, 4]} intensity={1.4} color="#fff3dc" />
      <pointLight position={[-3, -2, 3]} intensity={1.1} color={ringColor} />

      <group ref={groupRef}>
        {/* Outer calibrated brass frame */}
        <mesh>
          <torusGeometry args={[1.45, 0.035, 16, 96]} />
          <meshStandardMaterial color="#b99352" metalness={0.85} roughness={0.22} />
        </mesh>

        {/* Remaining budget arc */}
        <mesh rotation={[0, 0, Math.PI / 2]}>
          <torusGeometry args={[1.15, 0.11, 18, 90, arcAngle]} />
          <meshStandardMaterial
            color={ringColor}
            emissive={ringColor}
            emissiveIntensity={0.28}
            metalness={0.45}
            roughness={0.32}
          />
        </mesh>

        {/* Track groove */}
        <mesh>
          <torusGeometry args={[1.15, 0.03, 12, 80]} />
          <meshStandardMaterial color="#cfc2aa" metalness={0.3} roughness={0.6} transparent opacity={0.35} />
        </mesh>

        {/* 12 dial hour markers */}
        {ticks.map((angle, i) => (
          <mesh
            key={i}
            position={[Math.cos(angle) * 1.45, Math.sin(angle) * 1.45, 0]}
            rotation={[0, 0, angle]}
          >
            <boxGeometry args={[0.1, 0.025, 0.06]} />
            <meshStandardMaterial color="#9a742e" metalness={0.8} roughness={0.25} />
          </mesh>
        ))}

        {/* Central sovereign seal */}
        <mesh ref={sealRef}>
          <octahedronGeometry args={[0.52, 0]} />
          <meshStandardMaterial
            color={paused ? "#c8452b" : "#c89a4b"}
            emissive={paused ? "#8b2412" : "#6b4f1b"}
            emissiveIntensity={0.35}
            metalness={0.78}
            roughness={0.22}
          />
        </mesh>
      </group>

      <OrbitControls enableZoom={false} enablePan={false} enableDamping dampingFactor={0.08} />
    </>
  );
}

export default function BudgetVault3D({
  remainingRatio,
  paused,
}: {
  remainingRatio: number;
  paused: boolean;
}) {
  const reduced = useReducedMotion();
  const pct = Math.round(Math.max(0, Math.min(1, remainingRatio)) * 100);

  return (
    <div className="budget-vault-3d" aria-label={`3D budget gauge: ${pct}% remaining`}>
      <WebGLGuard
        fallback={
          <div className="vault-fallback">
            <span>{paused ? "LOCKED" : `${pct}%`}</span>
          </div>
        }
      >
        <Canvas dpr={[1, 2]} camera={{ position: [0, 0, 4.75], fov: 40 }} gl={{ alpha: true, antialias: true }}>
          <VaultDial remainingRatio={remainingRatio} paused={paused} reduced={reduced} />
        </Canvas>
      </WebGLGuard>
      <div className="vault-caption">
        {paused ? "PAUSED · SEAL LOCKED" : `${pct}% CAP REMAINING · 3D DIAL`}
      </div>
    </div>
  );
}
