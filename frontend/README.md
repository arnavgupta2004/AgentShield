# AgentShield frontend

React + Vite + TypeScript. Talks to the FastAPI backend in `/api` over
REST and WebSocket (see `src/lib/api.ts`); the dev server proxies `/api`
and `/ws` to `http://127.0.0.1:8000` (see `vite.config.ts`).

```bash
npm install
npm run dev -- --port 5173
```

Requires the backend running separately (`uvicorn api.main:app --port 8000`
from the repository root, inside the Python virtualenv). See the
repository root [README.md](../README.md) for full run instructions.

## Two evaluation paths, not one

The Live Demo tab's **System** selector offers two structurally different
things:

- **Baseline-Naive / Baseline-Strong / AgentShield** — run against the
  *local* engine process, streamed call-by-call over the WebSocket at
  `/ws/session/{id}` as the session graph builds live. This is what
  supports the node-by-node graph animation and the delay control.
- **AWS Lambda (live)** — evaluates the *same* fixture against the real
  deployed AWS endpoint (`infra/lambda_handler.py`, running the identical
  `engine.session_runner.run_session`) with a single request/response,
  because the deployed Lambda has no WebSocket/streaming route. The graph
  still renders (built from the fixture's calls plus the response's
  trace), just all at once rather than animated — and the Policy/Delay
  controls disable themselves for this option since neither applies to a
  single-shot call against the deployed stack's own bundled policy.

## Configuring the AWS endpoint: `VITE_AWS_API_BASE_URL`

`VITE_AWS_API_BASE_URL` (in `.env.development` / `.env.production` — see
`.env.example`) is the single place the deployed API's base URL is
configured; nothing else in the frontend hardcodes it. It's read in two
places, both from the same value:

- `src/lib/api.ts`'s `evaluateOnAws()` calls it via the `/aws-api` prefix.
- `vite.config.ts` reads it with Vite's `loadEnv()` to set the dev
  server's proxy target — not a second, independently-hardcoded copy.

If the variable is unset, the "AWS Lambda (live)" option simply doesn't
appear in the System selector, and the app behaves exactly as it does for
local-only development.

## Why `/aws-api` proxies instead of calling AWS directly

The deployed API Gateway has no CORS headers configured (see
`infra/template.yaml` / the root README's known limitations), so a
browser `fetch()` straight to the AWS URL is blocked by the browser's own
CORS enforcement — confirmed with a live OPTIONS/POST check before this
was built, not assumed. `vite.config.ts` proxies `/aws-api/*` to
`VITE_AWS_API_BASE_URL` server-side instead: the *dev server's* request to
AWS is a normal server-to-server call and isn't subject to CORS at all,
so the browser only ever talks to its own origin (`localhost:5173`).
This is a local-dev workaround, not a fix to the deployed stack --
serving this frontend as a public static site would need CORS enabled on
the API Gateway (a template change, intentionally not made without an
explicit decision to redeploy).
