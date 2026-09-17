import { useEffect, useRef, useState } from 'react'
import { fetchFixtures, fetchSystems, streamSession } from '../lib/api'
import type { CallEvent, Decision, FixtureSummary, Trace } from '../lib/types'
import GraphView from './GraphView'
import CompartmentTally from './CompartmentTally'
import DecisionBanner from './DecisionBanner'

const POLICY_VARIANTS = ['full', 'vendor_only']

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

  function run() {
    closeRef.current?.()
    setCalls([])
    setSelectedCallId(null)
    setFinalDecision(null)
    setRunning(true)

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
            {systems.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </label>

        <label>
          Policy
          <select value={policyVariant} onChange={(e) => setPolicyVariant(e.target.value)}>
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
