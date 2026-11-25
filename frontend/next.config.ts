import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Cache Components stays OFF: every page sits behind login and shows live, per-tenant data,
  // so there's nothing to prerender. Pages that read the session render per request.
  reactCompiler: true,
  // Do not generate AGENTS.md: no AI-agent notes in the repo (ROADMAP "zip problems" #11).
  agentRules: false,
  experimental: {
    serverActions: {
      // Default is 1 MB; uploads may be 10 MB plus multipart overhead.
      bodySizeLimit: "11mb",
    },
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
