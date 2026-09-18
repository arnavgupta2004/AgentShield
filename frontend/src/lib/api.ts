import type { BenchmarkResults, EvaluateResponse, FixtureDetail, FixtureSummary, StreamEvent } from './types'
import staticFixtures from '../data/fixtures.json'
import staticBenchmarkResults from '../data/benchmark-results.json'

// Single source of truth for the deployed AWS API's base URL -- see
// frontend/.env.example.
export const AWS_API_BASE_URL: string | undefined = import.meta.env.VITE_AWS_API_BASE_URL || undefined

// In a production build (e.g. deployed as a static site to AWS Amplify)
// there is no co-located FastAPI backend to serve /api/* or /ws/* --
// only the standalone AWS Lambda (see evaluateOnAws below) is reachable
// publicly, and this repo deliberately does not stand up a second
// backend just to serve the fixture picker and benchmark table. Local
// dev (`npm run dev`) is completely unaffected: it still calls the real
// local API exactly as before, every time. In production, fixture
// listing/detail and the benchmark table's *initial* view are instead
// served from bundled static data generated from this same repo's real
// fixtures/sessions.py and benchmark/results/results.json -- not
// invented data, just a different source for the identical values so
// the existing UI can render without a second backend. Re-running the
// benchmark or selecting a local-only system still requires a live
// local backend and will fail in production, same as it always would
// without one; nothing here fakes that they succeeded.
const STATIC_FIXTURES = staticFixtures as FixtureDetail[]
const STATIC_BENCHMARK_RESULTS = staticBenchmarkResults as BenchmarkResults

export async function fetchSystems(): Promise<string[]> {
  // No local backend in a static production build -- the local systems
  // (Baseline-Naive/Strong/AgentShield, which need /api and /ws) simply
  // aren't available there; only AWS_SYSTEM gets appended by the caller.
  if (import.meta.env.PROD) {
    return []
  }
  const res = await fetch('/api/systems')
  const data = await res.json()
  return data.systems
}

export async function fetchFixtures(): Promise<FixtureSummary[]> {
  if (import.meta.env.PROD) {
    return STATIC_FIXTURES.map((f) => ({
      session_id: f.session_id,
      category: f.category,
      expected_label: f.expected_label,
      expected_conflict_class: f.expected_conflict_class,
      num_calls: f.calls.length,
    }))
  }
  const res = await fetch('/api/fixtures')
  return res.json()
}

export async function fetchFixtureDetail(sessionId: string): Promise<FixtureDetail> {
  if (import.meta.env.PROD) {
    const found = STATIC_FIXTURES.find((f) => f.session_id === sessionId)
    if (!found) throw new Error(`unknown session_id ${sessionId}`)
    return found
  }
  const res = await fetch(`/api/fixtures/${encodeURIComponent(sessionId)}`)
  return res.json()
}

/** Evaluates a session against the real deployed AWS Lambda -- always a
 * single request/response (the deployed Lambda has no WebSocket/streaming
 * route), never a live per-call stream. In local dev this goes through
 * the dev server's same-origin /aws-api proxy (vite.config.ts), because
 * the deployed API previously had no CORS headers for a browser to call
 * it directly; in a production build there is no dev-server proxy to use,
 * so it calls AWS_API_BASE_URL directly instead (now safe now that the
 * API Gateway has CORS enabled -- see infra/template.yaml). */
export async function evaluateOnAws(sessionId: string, calls: FixtureDetail['calls']): Promise<EvaluateResponse> {
  const base = import.meta.env.PROD ? AWS_API_BASE_URL : '/aws-api'
  if (!base) throw new Error('VITE_AWS_API_BASE_URL is not configured')
  const res = await fetch(`${base}/sessions/${encodeURIComponent(sessionId)}/evaluate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, calls }),
  })
  if (!res.ok) {
    throw new Error(`AWS evaluate failed: HTTP ${res.status}`)
  }
  return res.json()
}

export async function fetchBenchmarkResults(): Promise<BenchmarkResults> {
  if (import.meta.env.PROD) {
    return STATIC_BENCHMARK_RESULTS
  }
  const res = await fetch('/api/benchmark/results')
  return res.json()
}

export async function runBenchmark(): Promise<BenchmarkResults> {
  const res = await fetch('/api/benchmark/run', { method: 'POST' })
  return res.json()
}

export function streamSession(
  sessionId: string,
  system: string,
  policyVariant: string,
  delayMs: number,
  onEvent: (event: StreamEvent) => void,
  onClose: () => void,
): () => void {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const url = `${proto}://${window.location.host}/ws/session/${encodeURIComponent(sessionId)}?system=${encodeURIComponent(system)}&policy_variant=${encodeURIComponent(policyVariant)}&delay_ms=${delayMs}`
  const ws = new WebSocket(url)
  ws.onmessage = (msg) => onEvent(JSON.parse(msg.data) as StreamEvent)
  ws.onclose = () => onClose()
  return () => ws.close()
}
