import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  ...(process.env.GITHUB_ACTIONS === "true"
    ? {
        basePath: "/book-recommender-system1",
        output: "export" as const,
        trailingSlash: true,
      }
    : {}),
};

export default nextConfig;
