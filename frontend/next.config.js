const nextConfig = {
  output: "standalone",
  skipTrailingSlashRedirect: true,
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
        ],
      },
    ];
  },
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
