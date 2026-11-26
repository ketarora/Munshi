"use client";

import { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { WebGLGuard, useReducedMotion } from "./WebGLGuard";

export type VoiceCoreMode = "idle" | "active" | "listening" | "readback" | "approval" | "blocked";

const MODE_COLORS: Record<VoiceCoreMode, { core: string; ring: string; accent: string }> = {
  idle: { core: "#8f7a56", ring: "#b99352", accent: "#3f5378" },
  active: { core: "#3f6b4f", ring: "#c89a4b", accent: "#7fb08f" },
  listening: { core: "#c8452b", ring: "#f07a58", accent: "#f4ecdc" },
  readback: { core: "#d49a3a", ring: "#f3c778", accent: "#c8452b" },
  approval: { core: "#e07a3f", ring: "#f2b86d", accent: "#7fb08f" },
  blocked: { core: "#b53324", ring: "#e2603f", accent: "#59606f" },
};

function BridgeScene({ mode, reduced }: { mode: VoiceCoreMode; reduced: boolean }) {
  const coreRef = useRef<THREE.Mesh>(null);
  const cageRef = useRef<THREE.Mesh>(null);
  const ring1Ref = useRef<THREE.Mesh>(null);
  const ring2Ref = useRef<THREE.Mesh>(null);
  const ring3Ref = useRef<THREE.Mesh>(null);
  const barsRef = useRef<THREE.Group>(null);
  const palette = MODE_COLORS[mode];

  const waveBars = useMemo(() => Array.from({ length: 28 }, (_, i) => i), []);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    const speed =
      mode === "listening" ? 2.4 : mode === "readback" ? 1.3 : mode === "active" ? 1.1 : 0.45;
    const pulse =
      mode === "listening"
        ? 1 + Math.sin(t * 7) * 0.14
        : mode === "readback"
          ? 1 + Math.sin(t * 3.5) * 0.08
          : 1 + Math.sin(t * 1.8) * 0.04;

    if (!reduced) {
      if (coreRef.current) {
        coreRef.current.rotation.y = t * 0.4 * speed;
        coreRef.current.rotation.x = Math.sin(t * 0.3) * 0.25;
        coreRef.current.scale.setScalar(pulse);
      }
      if (cageRef.current) {
        cageRef.current.rotation.y = -t * 0.35 * speed;
        cageRef.current.rotation.z = t * 0.2 * speed;
        cageRef.current.scale.setScalar(1.18 + (pulse - 1) * 0.6);
      }
      if (ring1Ref.current) {
        ring1Ref.current.rotation.z = t * 0.55 * speed;
        ring1Ref.current.rotation.x = Math.PI * 0.35 + Math.sin(t * 0.7) * 0.15;
      }
      if (ring2Ref.current) {
        ring2Ref.current.rotation.y = -t * 0.48 * speed;
        ring2Ref.current.rotation.x = -Math.PI * 0.28 + Math.cos(t * 0.6) * 0.14;
      }
      if (ring3Ref.current) {
        ring3Ref.current.rotation.z = -t * 0.3;
        ring3Ref.current.rotation.y = mode === "readback" ? 0 : t * 0.25;
      }
      if (barsRef.current) {
        barsRef.current.children.forEach((child, idx) => {
          const norm = idx / 27 - 0.5;
          const envelope = Math.exp(-norm * norm * 6);
          const amp = mode === "listening" ? 1.4 : mode === "active" ? 0.95 : mode === "readback" ? 0.8 : 0.32;
          const wave = Math.abs(Math.sin(t * (mode === "listening" ? 6.5 : 2.8) - idx * 0.42));
          const sy = 0.16 + wave * amp * (0.35 + envelope * 0.9);
          child.scale.y = sy;
        });
      }
    }
  });

  return (
    <>
      <ambientLight intensity={0.45} />
      <directionalLight position={[5, 6, 5]} intensity={1.5} color="#fff3dc" />
      <pointLight position={[-3.6, 0.5, 2]} intensity={1.8} color="#e2603f" distance={9} />
      <pointLight position={[3.6, 0.5, 2]} intensity={1.5} color="#7fb08f" distance={9} />
      <pointLight position={[0, 2.2, 2.5]} intensity={1.4} color={palette.ring} distance={8} />

      {/* Central Sovereign Acoustic Core */}
      <group position={[0, 0, 0]}>
        <mesh ref={coreRef}>
          <icosahedronGeometry args={[0.74, 2]} />
          <meshStandardMaterial
            color={palette.core}
            emissive={palette.core}
            emissiveIntensity={mode === "idle" ? 0.18 : 0.42}
            metalness={0.55}
            roughness={0.28}
          />
        </mesh>
        <mesh ref={cageRef}>
          <icosahedronGeometry args={[0.88, 1]} />
          <meshStandardMaterial
            color={palette.ring}
            wireframe
            metalness={0.8}
            roughness={0.2}
            transparent
            opacity={0.72}
          />
        </mesh>
        <mesh ref={ring1Ref}>
          <torusGeometry args={[1.22, 0.024, 16, 96]} />
          <meshStandardMaterial color={palette.ring} metalness={0.85} roughness={0.2} />
        </mesh>
        <mesh ref={ring2Ref}>
          <torusGeometry args={[1.42, 0.018, 14, 96]} />
          <meshStandardMaterial color={palette.accent} metalness={0.75} roughness={0.28} />
        </mesh>
        <mesh ref={ring3Ref} rotation={[Math.PI * 0.5, 0, 0]}>
          <torusGeometry args={[1.64, 0.012, 12, 110]} />
          <meshStandardMaterial
            color={mode === "readback" ? "#f3c778" : "#6f7787"}
            metalness={0.85}
            roughness={0.2}
            transparent
            opacity={mode === "readback" ? 0.95 : 0.45}
          />
        </mesh>
      </group>

      {/* Left Endpoint: Village Node (Amma) */}
      <group position={[-2.95, 0, 0]}>
        <mesh>
          <sphereGeometry args={[0.26, 24, 24]} />
          <meshStandardMaterial
            color="#e2603f"
            emissive="#c8452b"
            emissiveIntensity={0.45}
            metalness={0.4}
            roughness={0.35}
          />
        </mesh>
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.42, 0.014, 12, 48]} />
          <meshStandardMaterial color="#d4a359" metalness={0.8} roughness={0.25} />
        </mesh>
      </group>

      {/* Right Endpoint: Bengaluru Node (Rohit) */}
      <group position={[2.95, 0, 0]}>
        <mesh>
          <octahedronGeometry args={[0.28, 0]} />
          <meshStandardMaterial
            color="#7fb08f"
            emissive="#3f6b4f"
            emissiveIntensity={0.45}
            metalness={0.55}
            roughness={0.25}
          />
        </mesh>
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.44, 0.014, 12, 48]} />
          <meshStandardMaterial color="#8fa6cc" metalness={0.8} roughness={0.25} />
        </mesh>
      </group>

      {/* Acoustic Wave Bridge linking Village <-> Bengaluru */}
      <group ref={barsRef}>
        {waveBars.map((idx) => {
          const x = -2.45 + (idx / 27) * 4.9;
          const isCenter = Math.abs(x) < 1.05;
          return (
            <mesh key={idx} position={[x, 0, isCenter ? -0.35 : 0]}>
              <boxGeometry args={[0.055, 0.85, 0.055]} />
              <meshStandardMaterial
                color={x < 0 ? "#e2603f" : "#d4a359"}
                emissive={x < 0 ? "#c8452b" : "#9a742e"}
                emissiveIntensity={mode === "idle" ? 0.15 : 0.45}
                transparent
                opacity={isCenter ? 0.35 : 0.85}
                metalness={0.6}
                roughness={0.3}
              />
            </mesh>
          );
        })}
      </group>

      <OrbitControls
        enableZoom={false}
        enablePan={false}
        enableDamping
        dampingFactor={0.07}
        minPolarAngle={Math.PI * 0.25}
        maxPolarAngle={Math.PI * 0.72}
      />
    </>
  );
}

const MODE_LABEL: Record<VoiceCoreMode, string> = {
  idle: "Line standby · Start call dabaiye",
  active: "Voice bridge live · Verified caller",
  listening: "Awaaz sun raha hai · Listening",
  readback: "Rakam biller se · Read-back locked",
  approval: "Rohit ki manzoori ka intezaar",
  blocked: "Niyam ne roka · Zero spend",
};

export default function VoiceCore3D({ mode }: { mode: VoiceCoreMode }) {
  const reduced = useReducedMotion();

  const fallback = (
    <div className="voice-core-fallback">
      <div className="core-ring" />
      <span>{MODE_LABEL[mode]}</span>
    </div>
  );

  return (
    <div className="voice-core-3d" aria-label="Interactive 3D voice bridge">
      <WebGLGuard fallback={fallback}>
        <Canvas dpr={[1, 2]} camera={{ position: [0, 0.35, 5.1], fov: 40 }} gl={{ alpha: true, antialias: true }}>
          <BridgeScene mode={mode} reduced={reduced} />
        </Canvas>
      </WebGLGuard>
      <div className="core-hud">
        <span className="core-hud-pill">
          <span className={`core-dot ${mode}`} />
          {MODE_LABEL[mode]}
        </span>
        <span className="core-hud-hint">3D spatial bridge · drag to orbit</span>
      </div>
    </div>
  );
}

