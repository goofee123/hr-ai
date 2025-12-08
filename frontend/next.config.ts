import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Output standalone for Docker deployments
  output: "standalone",

  // Rewrites to proxy API requests to FastAPI backend in development
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: process.env.NEXT_PUBLIC_API_URL
          ? `${process.env.NEXT_PUBLIC_API_URL}/:path*`
          : "http://localhost:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
