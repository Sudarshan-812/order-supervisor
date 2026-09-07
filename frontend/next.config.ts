import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // This app is the workspace root; ignore stray lockfiles higher up the tree.
  outputFileTracingRoot: path.join(__dirname),
  async rewrites() {
    // Proxy API calls to the FastAPI backend during dev.
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.BACKEND_URL ?? "http://localhost:8000"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
