/** @type {import('next').NextConfig} */
const nextConfig = {
  // Duplicate Strict Mode fetches make every job/question load twice in dev.
  reactStrictMode: false,
  eslint: {
    ignoreDuringBuilds: true,
  },
};

module.exports = nextConfig;
