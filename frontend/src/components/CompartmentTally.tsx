import type { Trace } from '../lib/types'

export default function CompartmentTally({ trace }: { trace: Trace | null }) {
  if (!trace) {
    return <div className="panel muted-panel">Select a sink call (send_notification / create_draft_payment) to see its compartment tally.</div>
  }

  if (trace.matches.length === 0) {
    return <div className="panel muted-panel">No conflict-class members present among this call's ancestors.</div>
  }

  return (
    <div className="panel">
      <h3>Compartment tally — {trace.tool}{trace.recipient ? ` → ${trace.recipient}` : ''}</h3>
      <table className="tally-table">
        <thead>
          <tr>
            <th>Conflict class</th>
            <th>Members involved</th>
            <th>Count</th>
            <th>Threshold</th>
            <th>Verdict</th>
          </tr>
        </thead>
        <tbody>
          {trace.matches.map((m) => (
            <tr key={m.conflict_class}>
              <td>{m.conflict_class}</td>
              <td>
                <div className="chip-list">
                  {m.member_compartments_involved.map((mc) => (
                    <span key={mc} className="chip">{mc}</span>
                  ))}
                </div>
              </td>
              <td>{m.actual_count}</td>
              <td>{m.clearance_threshold}{m.margin ? ` (+${m.margin} margin)` : ''}</td>
              <td>
                <span className={`badge badge-${m.verdict.toLowerCase()}`}>{m.verdict}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="ancestor-note">
        Ancestor calls considered: {trace.ancestor_call_ids.length ? trace.ancestor_call_ids.join(', ') : 'none'}
      </div>
    </div>
  )
}
