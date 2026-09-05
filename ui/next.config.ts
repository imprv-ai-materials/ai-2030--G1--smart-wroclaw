import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emits a self-contained server bundle at .next/standalone so a container
  // runtime image doesn't need pnpm or the full node_modules.
  output: "standalone",
  // Hide the floating dev-tools indicator during normal development. Next.js
  // still surfaces the error indicator/overlay when there's a compile or
  // runtime error, so the button only shows up when something is wrong.
  devIndicators: false,
};

export default nextConfig;
