import path from "node:path";
import type { NextConfig } from "next";

// One `.env` at the repo root serves both apps. Next.js only reads env files
// from `web/`, so load the root file here. Variables already set in the
// environment (for example by Docker) win.
try {
  process.loadEnvFile(path.join(__dirname, "..", ".env"));
} catch {
  // No root .env file: fine, rely on the real environment.
}

const API_URL = process.env.API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // The end-to-end test runs its own dev server next to `make dev`; a separate
  // build folder keeps the two from fighting over the same files.
  distDir: process.env.NEXT_PUBLIC_E2E === "1" ? ".next-e2e" : ".next",
  cacheComponents: true,
  partialPrefetching: true,
  output: "standalone",
  // Where Clerk sends people to sign in (used by server-side auth checks too).
  env: {
    NEXT_PUBLIC_CLERK_SIGN_IN_URL: "/sign-in",
    NEXT_PUBLIC_CLERK_SIGN_UP_URL: "/sign-up",
  },
  turbopack: {
    root: __dirname,
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  // The browser only ever talks to this origin; /api is forwarded to FastAPI.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default nextConfig;
