/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  // Hide Next.js' development indicator; the app already surfaces its own errors.
  devIndicators: false,
  turbopack: {
    root: import.meta.dirname,
  },
};

export default nextConfig;
