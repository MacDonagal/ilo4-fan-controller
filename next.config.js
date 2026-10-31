/** @type {import('next').NextConfig} */
module.exports = {
    reactStrictMode: true,
    swcMinify: true,
    // Self-contained server bundle: much smaller Docker image, no yarn at runtime
    output: "standalone",
    poweredByHeader: false,
};
