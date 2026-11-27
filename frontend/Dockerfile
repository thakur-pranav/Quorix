# syntax=docker/dockerfile:1
# Quorix web app (Next.js). Three stages: install → build → a runtime image that holds only the
# standalone server, not the source, the dev dependencies or pnpm.

ARG NODE_VERSION=22

# --- deps: install exactly what the lockfile says --------------------------------------------
FROM node:${NODE_VERSION}-bookworm-slim AS deps
WORKDIR /app
# corepack provides the pnpm version pinned in package.json ("packageManager").
RUN corepack enable
# pnpm-workspace.yaml holds the install-script policy (allowBuilds): same install as CI.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN COREPACK_ENABLE_DOWNLOAD_PROMPT=0 pnpm install --frozen-lockfile

# --- build ------------------------------------------------------------------------------------
FROM node:${NODE_VERSION}-bookworm-slim AS build
WORKDIR /app
RUN corepack enable
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_OUTPUT=standalone \
    NEXT_TELEMETRY_DISABLED=1
# No secrets at build time: the env is validated when the server starts (instrumentation.ts).
RUN COREPACK_ENABLE_DOWNLOAD_PROMPT=0 pnpm build

# --- runtime ----------------------------------------------------------------------------------
FROM node:${NODE_VERSION}-bookworm-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# The node image's built-in non-root user.
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
# Static files (the logo): standalone output copies neither public/ nor .next/static itself.
COPY --from=build --chown=node:node /app/public ./public
USER node
EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD node -e "fetch('http://127.0.0.1:' + process.env.PORT + '/login').then((r) => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"

CMD ["node", "server.js"]
