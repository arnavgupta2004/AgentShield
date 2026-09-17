import type { BenchmarkResults, FixtureSummary, StreamEvent } from './types'

export async function fetchSystems(): Promise<string[]> {
  const res = await fetch('/api/systems')
  const data = await res.json()
  return data.systems
}

export async function fetchFixtures(): Promise<FixtureSummary[]> {
  const res = await fetch('/api/fixtures')
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
