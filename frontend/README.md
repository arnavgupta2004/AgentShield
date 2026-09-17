# AgentShield frontend

React + Vite + TypeScript. Talks to the FastAPI backend in `/api` over
REST and WebSocket (see `src/lib/api.ts`); the dev server proxies
`/api` and `/ws` to `http://127.0.0.1:8000` (see `vite.config.ts`).

```bash
npm install
npm run dev -- --port 5173
```

Requires the backend running separately (`uvicorn api.main:app --port 8000`
from the repository root, inside the Python virtualenv). See the
repository root [README.md](../README.md) for full run instructions.
