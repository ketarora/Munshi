"use client";

import { useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { WebGLGuard, useReducedMotion } from "./WebGLGuard";

function HelixChain({
  entries,
  ok,
  firstBadSeq,
  reduced,
}: {
  entries: number;
  ok: boolean;
  firstBadSeq: number | null;
  reduced: boolean;
}) {
  const groupRef = useRef<THREE.Group>(null);
  const count = Math.max(3, Math.min(12, entries || 4));
  const nodes = Array.from({ length: count }, (_, idx) => idx);

  useFrame(({ clock }) => {
    if (reduced || !groupRef.current) return;
    groupRef.current.rotation.y = clock.getElapsedTime() * 0.25;
  });

  return (
    <>
      <ambientLight intensity={0.5} />
      <directionalLight position={[5, 5, 5]} intensity={1.4} color="#f5efe2" />
      <pointLight position={[-4, 0, 3]} intensity={1.4} color={ok ? "#7fb08f" : "#e2603f"} />

      <group ref={groupRef}>
        {nodes.map((idx) => {
          const x = -((count - 1) * 0.56) / 2 + idx * 0.56;
          const angle = idx * 0.65;
          const y = Math.sin(angle) * 0.36;
          const z = Math.cos(angle) * 0.36;
          const isBad = !ok && (firstBadSeq === null || idx + 1 >= firstBadSeq);
          const color = isBad ? "#c8452b" : idx % 2 === 0 ? "#d4a359" : "#7fb08f";
          return (
            <group key={idx} position={[x, y, z]}>
              <mesh rotation={[angle * 0.4, angle * 0.7, 0]}>
                <boxGeometry args={[0.28, 0.28, 0.28]} />
                <meshStandardMaterial
                  color={color}
                  emissive={color}
                  emissiveIntensity={0.28}
                  metalness={0.7}
                  roughness={0.25}
                />
              </mesh>
              {idx < count - 1 ? (
                <mesh position={[0.28, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
                  <cylinderGeometry args={[0.024, 0.024, 0.48, 8]} />
                  <meshStandardMaterial
                    color={isBad ? "#e2603f" : "#60708a"}
                    metalness={0.6}
                    roughness={0.35}
                  />
                </mesh>
              ) : null}
            </group>
          );
        })}
      </group>

      <OrbitControls enableZoom={false} enablePan={false} enableDamping dampingFactor={0.07} />
    </>
  );
}

export default function AuditChain3D({
  entries,
  ok,
  firstBadSeq,
}: {
  entries: number;
  ok: boolean;
  firstBadSeq: number | null;
}) {
  const reduced = useReducedMotion();

  return (
    <div className="audit-chain-3d" aria-label={`3D SHA-256 audit chain: ${entries} entries`}>
      <WebGLGuard
        fallback={
          <div className="vault-fallback">
            <span>{ok ? `VALID · ${entries} LINKS` : "CHAIN TAMPERED"}</span>
          </div>
        }
      >
        <Canvas dpr={[1, 2]} camera={{ position: [0, 0.4, 4.6], fov: 38 }} gl={{ alpha: true, antialias: true }}>
          <HelixChain entries={entries} ok={ok} firstBadSeq={firstBadSeq} reduced={reduced} />
        </Canvas>
      </WebGLGuard>
      <div className="audit-3d-badge">
        {ok ? `SHA-256 HASH CHAIN VERIFIED · ${entries} BLOCKS` : `TAMPER DETECTED @ SEQ ${firstBadSeq}`}
      </div>
    </div>
  );
}

