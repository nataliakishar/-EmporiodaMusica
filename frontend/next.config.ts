import type { NextConfig } from "next";

const config: NextConfig = {
  poweredByHeader: false,
  experimental: { cpus: 1 }, // limita processos de geração no desenvolvimento local
  async headers() {
    return [{ source: "/:path*", headers: [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "X-Frame-Options", value: "DENY" },
    ] }];
  },
};
export default config;
