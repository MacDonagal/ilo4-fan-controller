# syntax=docker/dockerfile:1
FROM node:24-alpine AS node-base
RUN corepack enable && corepack install --global yarn@1.22.22

FROM node-base AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile

FROM node-base AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY . .
COPY --from=deps /app/node_modules ./node_modules
RUN yarn build

# Runtime: plain node, no yarn/corepack, only the standalone bundle
FROM node:24-alpine AS runner
WORKDIR /app

LABEL org.opencontainers.image.title="iLO4 Fan Controller" \
      org.opencontainers.image.description="Web UI + REST API to control HP iLO4 (Gen8) fan speeds" \
      org.opencontainers.image.source="https://github.com/DavidIlie/ilo4-fan-controller"

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN apk add --no-cache tini \
    && addgroup -g 1001 -S nodejs \
    && adduser -S nextjs -u 1001 -G nodejs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --chmod=755 docker/entrypoint.sh /usr/local/bin/entrypoint.sh

USER nextjs
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD wget -qO /dev/null "http://127.0.0.1:${PORT}/api/health" || exit 1

# tini = proper PID 1 (signals, zombie reaping)
ENTRYPOINT ["/sbin/tini", "--", "/usr/local/bin/entrypoint.sh"]
CMD ["node", "server.js"]
