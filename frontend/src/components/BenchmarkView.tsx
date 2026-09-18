import { useEffect, useState } from 'react'
import { fetchBenchmarkResults, runBenchmark } from '../lib/api'
import type { BenchmarkResults } from '../lib/types'

const SYSTEM_ORDER = ['Baseline-Naive', 'Baseline-Strong', 'AgentShield']

export default function BenchmarkView() {
  const [results, setResults] = useState<BenchmarkResults | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetchBenchmarkResults().then(setResults)
  }, [])

  async function reRun() {
    setLoading(true)
    try {
      setResults(await runBenchmark())
    } catch (err) {
      alert(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  if (!results) return <div className="panel muted-panel">Loading benchmark results…</div>

  return (
    <div className="benchmark-view">
      <div className="panel">
        <div className="benchmark-header">
          <h3>30-session benchmark — {results.total_sessions} sessions, real backend runs (not simulated)</h3>
          <button onClick={reRun} disabled={loading}>{loading ? 'Running…' : 'Re-run benchmark'}</button>
        </div>

        <table className="tally-table">
          <thead>
            <tr>
              <th>System</th>
              <th>TP</th><th>FP</th><th>TN</th><th>FN</th>
              <th>Precision</th><th>Recall</th><th>F1</th>
              <th>FPR (benign subset)</th>
              <th>Attack 1</th>
              <th>Attack 2</th>
            </tr>
          </thead>
          <tbody>
            {SYSTEM_ORDER.map((system) => {
              const m = results.metrics[system]
              if (!m) return null
              const attack2 = results.attack_breakdown[`${system}::attack2`]
              const attack2Miss = system === 'Baseline-Strong' && attack2 === '0/6'
              return (
                <tr key={system} className={system === 'AgentShield' ? 'row-highlight' : ''}>
                  <td>{system}</td>
                  <td>{m.tp}</td><td>{m.fp}</td><td>{m.tn}</td><td>{m.fn}</td>
                  <td>{m.precision.toFixed(2)}</td>
                  <td>{m.recall.toFixed(2)}</td>
                  <td>{m.f1.toFixed(2)}</td>
                  <td>{(results.false_positive_rate_benign_subset[system] * 100).toFixed(0)}%</td>
                  <td>{results.attack_breakdown[`${system}::attack1`]}</td>
                  <td className={attack2Miss ? 'cell-warning' : ''}>
                    {attack2}{attack2Miss ? ' — misses Attack 2 (expected, honest gap)' : ''}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="panel">
        <h3>Per-session results</h3>
        <div className="session-table-scroll">
          <table className="tally-table small">
            <thead>
              <tr>
                <th>Session</th><th>Category</th><th>System</th>
                <th>Expected</th><th>Actual</th><th>Matched class</th><th>Pass</th>
              </tr>
            </thead>
            <tbody>
              {results.rows.map((r) => (
                <tr key={`${r.session_id}-${r.system}`}>
                  <td>{r.session_id}</td>
                  <td>{r.category}</td>
                  <td>{r.system}</td>
                  <td>{r.expected_label}</td>
                  <td>{r.actual_decision}</td>
                  <td>{r.matched_conflict_class ?? '—'}</td>
                  <td>{r.passed ? '✓' : '✗'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
