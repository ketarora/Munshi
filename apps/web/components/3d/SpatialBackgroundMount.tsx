"use client";

import AmbientBackground from "@/components/AmbientBackground";
import SpatialAtmosphere3D from "@/components/3d/SpatialAtmosphere3D";

export default function SpatialBackgroundMount() {
  return (
    <>
      <AmbientBackground />
      <SpatialAtmosphere3D />
    </>
  );
}
