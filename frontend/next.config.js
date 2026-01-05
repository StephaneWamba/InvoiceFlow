/** @type {import('next').NextConfig} */
const nextConfig = {
  // Only use standalone output in production
  ...(process.env.NODE_ENV === 'production' && { output: 'standalone' }),
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8100',
  },
  // Enable webpack polling for Docker hot reload
  webpack: (config, { isServer }) => {
    if (!isServer) {
      config.watchOptions = {
        poll: 1000, // Check for changes every second
        aggregateTimeout: 300, // Delay before rebuilding once the first file changed
      }
    }
    return config
  },
}

module.exports = nextConfig

