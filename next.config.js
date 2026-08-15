/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Babel (.babelrc) compiles the app. SWC minify is off because the
  // @next/swc-win32-x64-msvc native binary failed to install on this machine.
  swcMinify: false,
  eslint: {
    ignoreDuringBuilds: true,
  },
};

module.exports = nextConfig;
