import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  transpilePackages: ["framer-motion", "three"],
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
