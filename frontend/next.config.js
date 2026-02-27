const nextConfig = {
  output: "standalone",
  skipTrailingSlashRedirect: true,
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";
    return {
      beforeFiles: [
        {
          source: "/api/:path(.*)",
          destination: `${backendUrl}/api/:path`,
        },
        {
          source: "/ws/:path(.*)",
          destination: `${backendUrl}/ws/:path`,
        },
      ],
    };
  },
};

module.exports = nextConfig;
