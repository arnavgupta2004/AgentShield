import { useEffect, useRef, useState } from 'react'
import { AWS_API_BASE_URL, evaluateOnAws, fetchFixtureDetail, fetchFixtures, fetchSystems, streamSession } from '../lib/api'
import type { CallEvent, Decision, FixtureSummary, Trace } from '../lib/types'
import GraphView from './GraphView'
import CompartmentTally from './CompartmentTally'
import DecisionBanner from './DecisionBanner'

const POLICY_VARIANTS = ['full', 'vendor_only']
const AWS_SYSTEM = 'AWS Lambda (live)'
const SINK_TOOLS = new Set(['create_draft_payment', 'send_notification'])

export default function SessionRunner() {
  const [fixtures, setFixtures] = useState<FixtureSummary[]>([])
  const [systems, setSystems] = useState<string[]>([])
  const [sessionId, setSessionId] = useState('')
  const [system, setSystem] = useState('AgentShield')
  const [policyVariant, setPolicyVariant] = useState('full')
  const [delayMs, setDelayMs] = useState(150)

  const [calls, setCalls] = useState<CallEvent[]>([])
  const [selectedCallId, setSelectedCallId] = useState<string | null>(null)
  const [finalDecision, setFinalDecision] = useState<Decision | null>(null)
  const [expectedLabel, setExpectedLabel] = useState<Decision | null>(null)
  const [running, setRunning] = useState(false)

  const closeRef = useRef<(() => void) | null>(null)

  useEffect(() => {
    fetchFixtures().then((fx) => {
      setFixtures(fx)
      if (fx.length) setSessionId(fx[0].session_id)
    })
    fetchSystems().then(setSystems)
    return () => closeRef.current?.()
  }, [])

  const grouped = fixtures.reduce<Record<string, FixtureSummary[]>>((acc, f) => {
    ;(acc[f.category] ??= []).push(f)
    return acc
  }, {})

  const allSystems = AWS_API_BASE_URL ? [...systems, AWS_SYSTEM] : systems

  async function runOnAws() {
    const fixture = await fetchFixtureDetail(sessionId)
    setExpectedLabel(fixture.expected_label)

    const response = await evaluateOnAws(sessionId, fixture.calls)
    const traceByCallId = new Map(response.traces.map((t) => [t.call_id, t]))

    // The deployed Lambda has no streaming route, so this renders the
    // whole (real, backend-computed) result at once rather than
    // node-by-node -- every value below comes from `response`, none of
    // it is computed client-side.
    const builtCalls: CallEvent[] = fixture.calls.map((c, i) => {
      const callId = `${sessionId}-c${i + 1}`
      const isSink = SINK_TOOLS.has(c.tool)
      const trace = traceByCallId.get(callId) ?? null
      return {
        type: 'call',
        call_id: callId,
        tool: c.tool,
        resource_id: c.resource_id,
        vendor_id: c.vendor_id,
        period: c.period,
        recipient: c.recipient,
        is_sink: isSink,
        compartment_tags: {},
        decision: trace?.decision ?? 'ALLOW',
        trace,
      }
    })
    setCalls(builtCalls)
    const lastSink = [...builtCalls].reverse().find((c) => c.is_sink)
    if (lastSink) setSelectedCallId(lastSink.call_id)
    setFinalDecision(response.final_decision)
  }

  function run() {
    closeRef.current?.()
    setCalls([])
    setSelectedCallId(null)
    setFinalDecision(null)
    setRunning(true)

    if (system === AWS_SYSTEM) {
      runOnAws()
        .catch((err) => alert(err instanceof Error ? err.message : String(err)))
        .finally(() => setRunning(false))
      return
    }

    closeRef.current = streamSession(
      sessionId,
      system,
      policyVariant,
      delayMs,
      (event) => {
        if (event.type === 'session_start') {
          setExpectedLabel(event.expected_label)
        } else if (event.type === 'call') {
          setCalls((prev) => [...prev, event])
          if (event.is_sink) setSelectedCallId(event.call_id)
        } else if (event.type === 'session_complete') {
          setFinalDecision(event.final_decision)
          setRunning(false)
        } else if (event.type === 'error') {
          setRunning(false)
          alert(event.message)
        }
      },
      () => setRunning(false),
    )
  }

  const selectedTrace: Trace | null =
    calls.find((c) => c.call_id === selectedCallId)?.trace ?? null
  const allTraces = calls.filter((c) => c.trace).map((c) => c.trace as Trace)

  return (
    <div className="session-runner">
      <div className="controls panel">
        <label>
          Session
          <select value={sessionId} onChange={(e) => setSessionId(e.target.value)}>
            {Object.entries(grouped).map(([category, items]) => (
              <optgroup key={category} label={category}>
                {items.map((f) => (
                  <option key={f.session_id} value={f.session_id}>
                    {f.session_id} ({f.expected_label})
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>

        <label>
          System
          <select value={system} onChange={(e) => setSystem(e.target.value)}>
            {allSystems.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </label>

        <label>
          Policy
          <select
            value={policyVariant}
            onChange={(e) => setPolicyVariant(e.target.value)}
            disabled={system === AWS_SYSTEM}
            title={system === AWS_SYSTEM ? 'The deployed Lambda always uses its bundled full policy' : undefined}
          >
            {POLICY_VARIANTS.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </label>

        <label>
          Delay (ms)
          <input
            type="number"
            min={0}
            max={2000}
            step={50}
            value={delayMs}
            onChange={(e) => setDelayMs(Number(e.target.value))}
            disabled={system === AWS_SYSTEM}
            title={system === AWS_SYSTEM ? 'AWS Lambda has no streaming route -- result arrives all at once' : undefined}
          />
        </label>

        <button onClick={run} disabled={running || !sessionId} className="run-button">
          {running ? 'Running…' : 'Run session'}
        </button>
      </div>

      <div className="panel">
        <h3>Session graph</h3>
        <GraphView calls={calls} selectedCallId={selectedCallId} onSelect={setSelectedCallId} />
      </div>

      <DecisionBanner finalDecision={finalDecision} expectedLabel={expectedLabel} traces={allTraces} />

      <CompartmentTally trace={selectedTrace} />
    </div>
  )
}
