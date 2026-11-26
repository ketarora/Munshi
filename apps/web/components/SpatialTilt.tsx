"use client";

import { useRef, useState, type ReactNode } from "react";
import { useReducedMotion } from "./3d/WebGLGuard";

export default function SpatialTilt({
  children,
  className = "",
  maxTilt = 6,
}: {
  children: ReactNode;
  className?: string;
  maxTilt?: number;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const reduced = useReducedMotion();
  const [transform, setTransform] = useState("perspective(1200px) rotateX(0deg) rotateY(0deg)");
  const [glare, setGlare] = useState({ x: 50, y: 50, opacity: 0 });

  const onMove = (event: React.MouseEvent<HTMLDivElement>) => {
    if (reduced || !ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const px = (event.clientX - rect.left) / rect.width;
    const py = (event.clientY - rect.top) / rect.height;
    const rx = (0.5 - py) * maxTilt * 2;
    const ry = (px - 0.5) * maxTilt * 2;
    setTransform(`perspective(1200px) rotateX(${rx.toFixed(2)}deg) rotateY(${ry.toFixed(2)}deg)`);
    setGlare({ x: Math.round(px * 100), y: Math.round(py * 100), opacity: 0.14 });
  };

  const onLeave = () => {
    setTransform("perspective(1200px) rotateX(0deg) rotateY(0deg)");
    setGlare((prev) => ({ ...prev, opacity: 0 }));
  };

  return (
    <div
      ref={ref}
      className={`spatial-tilt ${className}`}
      onMouseMove={onMove}
      onMouseLeave={onLeave}
      style={{ transform }}
    >
      <div
        className="spatial-tilt-glare"
        aria-hidden="true"
        style={{
          opacity: glare.opacity,
          background: `radial-gradient(circle at ${glare.x}% ${glare.y}%, rgba(255, 240, 210, 0.55), transparent 60%)`,
        }}
      />
      {children}
    </div>
  );
}

