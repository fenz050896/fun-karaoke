import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'standalone',
  allowedDevOrigins: ['df-karaoke.duckdns.org', 'karaoke.defigroup.id'],
};

export default nextConfig;
