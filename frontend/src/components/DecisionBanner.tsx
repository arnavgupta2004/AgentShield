import { useState } from 'react'
import type { Decision, Trace } from '../lib/types'

interface Props {
  finalDecision: Decision | null
  expectedLabel: Decision | null
  traces: Trace[]
}

export default function DecisionBanner({ finalDecision, expectedLabel, traces }: Props) {
  const [expanded, setExpanded] = useState(false)

  if (!finalDecision) {
    return <div className="panel muted-panel">Run a session to see its decision.</div>
  }

  const matches = expectedLabel ? finalDecision === expectedLabel : null

  return (
    <div className={`decision-banner decision-${finalDecision.toLowerCase()}`}>
      <div className="decision-banner-main">
        <span className="decision-label">{finalDecision}</span>
        {expectedLabel && (
          <span className="decision-expected">
            expected {expectedLabel} — {matches ? 'matches ✓' : 'MISMATCH ✗'}
          </span>
        )}
        <button className="link-button" onClick={() => setExpanded((e) => !e)}>
          {expanded ? 'hide trace' : 'show trace'}
        </button>
      </div>
      {expanded && (
        <pre className="trace-dump">{JSON.stringify(traces, null, 2)}</pre>
      )}
    </div>
  )
}
