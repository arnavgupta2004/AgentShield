import type { BenchmarkResults, EvaluateResponse, FixtureDetail, FixtureSummary, StreamEvent } from './types'

// Single source of truth for the deployed AWS API's base URL -- see
// frontend/.env.example. Requests still go through the dev server's
// same-origin /aws-api proxy (vite.config.ts), which forwards to this
// same value server-side, because the deployed API has no CORS headers
// for a browser to call it directly (see infra/template.yaml).
export const AWS_API_BASE_URL: string | undefined = import.meta.env.VITE_AWS_API_BASE_URL || undefined

export async function fetchSystems(): Promise<string[]> {
  const res = await fetch('/api/systems')
  const data = await res.json()
  return data.systems
}

export async function fetchFixtures(): Promise<FixtureSummary[]> {
  const res = await fetch('/api/fixtures')
  return res.json()
}

export async function fetchFixtureDetail(sessionId: string): Promise<FixtureDetail> {
  const res = await fetch(`/api/fixtures/${encodeURIComponent(sessionId)}`)
  return res.json()
}

/** Evaluates a session against the real deployed AWS Lambda, via the dev
 * server's /aws-api proxy. This is a single request/response (the deployed
 * Lambda has no WebSocket/streaming route), not a live per-call stream. */
export async function evaluateOnAws(sessionId: string, calls: FixtureDetail['calls']): Promise<EvaluateResponse> {
  const res = await fetch(`/aws-api/sessions/${encodeURIComponent(sessionId)}/evaluate`, {
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
