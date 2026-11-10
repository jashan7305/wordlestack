# WordleStack frontend

React, TypeScript, Vite, and Tailwind CSS v4 client for WordleStack. The app is served from FastAPI in Docker; Vite proxies `/api` to `http://localhost:8000` for local development.

```sh
pnpm install
pnpm dev
```

Run the gameplay tests with `pnpm test`, then check with `pnpm lint`, `pnpm typecheck`, and `pnpm build`. See the root README for backend and deployment setup.
