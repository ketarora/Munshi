"use client";

import { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { WebGLGuard, useReducedMotion } from "./WebGLGuard";

function MeridianScene({ reduced }: { reduced: boolean }) {
  const groupRef = useRef<THREE.Group>(null);
  const pointsRef = useRef<THREE.Points>(null);

  const particlePositions = useMemo(() => {
    const count = 180;
    const arr = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const angle = (i * 137.5 * Math.PI) / 180;
      const radius = 3.2 + ((i * 17) % 65) / 10;
      arr[i * 3] = Math.cos(angle) * radius;
      arr[i * 3 + 1] = (((i * 29) % 100) / 100 - 0.5) * 9;
      arr[i * 3 + 2] = Math.sin(angle) * radius - 3;
    }
    return arr;
  }, []);

  useFrame(({ clock, pointer }) => {
    if (reduced) return;
    const t = clock.getElapsedTime();
    if (groupRef.current) {
      groupRef.current.rotation.y = t * 0.035 + pointer.x * 0.14;
      groupRef.current.rotation.x = Math.sin(t * 0.08) * 0.06 + pointer.y * 0.08;
    }
    if (pointsRef.current) {
      pointsRef.current.rotation.y = -t * 0.02;
    }
  });

  return (
    <>
      <ambientLight intensity={0.4} />
      <pointLight position={[6, 6, 4]} intensity={1.2} color="#d4a359" />
      <pointLight position={[-6, -4, 3]} intensity={0.9} color="#c8452b" />
      <group ref={groupRef} position={[1.6, 0.2, -3.5]}>
        <mesh rotation={[Math.PI * 0.36, 0.2, 0]}>
          <torusGeometry args={[4.4, 0.012, 12, 120]} />
          <meshStandardMaterial color="#b99352" metalness={0.8} roughness={0.25} transparent opacity={0.24} />
        </mesh>
        <mesh rotation={[-Math.PI * 0.28, 0.5, 0.4]}>
          <torusGeometry args={[3.4, 0.01, 12, 110]} />
          <meshStandardMaterial color="#c8452b" metalness={0.65} roughness={0.35} transparent opacity={0.18} />
        </mesh>
        <mesh rotation={[0.9, -0.3, 0.2]}>
          <torusGeometry args={[5.3, 0.008, 10, 140]} />
          <meshStandardMaterial color="#3c527a" metalness={0.7} roughness={0.3} transparent opacity={0.16} />
        </mesh>
      </group>
      <points ref={pointsRef}>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            args={[particlePositions, 3]}
          />
        </bufferGeometry>
        <pointsMaterial size={0.045} color="#c89348" transparent opacity={0.42} sizeAttenuation />
      </points>
    </>
  );
}

export default function SpatialAtmosphere3D() {
  const reduced = useReducedMotion();

  return (
    <div className="spatial-backdrop" aria-hidden="true">
      <WebGLGuard fallback={null}>
        <Canvas
          dpr={1}
          camera={{ position: [0, 0, 7], fov: 45 }}
          gl={{ alpha: true, antialias: false, powerPreference: "low-power" }}
          style={{ pointerEvents: "none" }}
        >
          <MeridianScene reduced={reduced} />
        </Canvas>
      </WebGLGuard>
    </div>
  );
}
