# Quorix frontend

Next.js (App Router) + TypeScript + Tailwind + MongoDB (users only).
The browser talks only to this app; this app's server talks to the FastAPI backend with a
signed 60-second service token (`src/lib/fastapi/client.ts`).

## Run locally

```bash
cp .env.example .env.local        # then fill in the secrets (see the file)
corepack pnpm install
corepack pnpm dev                 # http://localhost:3000 (backend must run on :8000)
```

## Checks

```bash
corepack pnpm test                # Vitest unit tests
corepack pnpm typecheck && corepack pnpm lint && corepack pnpm build
corepack pnpm test:e2e            # Playwright: needs MongoDB, the backend and the dev server
```
