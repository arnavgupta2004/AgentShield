import { useMemo } from 'react'
import type { CallEvent } from '../lib/types'
import { colorFor } from '../lib/colors'

interface Props {
  calls: CallEvent[]
  selectedCallId: string | null
  onSelect: (callId: string) => void
}

const NODE_W = 150
const NODE_H = 56
const GAP_X = 40
const TOP = 30

export default function GraphView({ calls, selectedCallId, onSelect }: Props) {
  const positions = useMemo(() => {
    const map = new Map<string, { x: number; y: number }>()
    calls.forEach((c, i) => {
      map.set(c.call_id, { x: 20 + i * (NODE_W + GAP_X), y: TOP })
    })
    return map
  }, [calls])

  const width = Math.max(600, 20 + calls.length * (NODE_W + GAP_X))
  const height = TOP + NODE_H + 40

  const selected = calls.find((c) => c.call_id === selectedCallId)
  const ancestorIds = new Set(selected?.trace?.ancestor_call_ids ?? [])

  return (
    <div className="graph-scroll">
      <svg width={width} height={height} className="graph-svg">
        {selected &&
          [...ancestorIds].map((ancestorId) => {
            const from = positions.get(ancestorId)
            const to = positions.get(selected.call_id)
            if (!from || !to) return null
            return (
              <line
                key={ancestorId}
                x1={from.x + NODE_W / 2}
                y1={from.y + NODE_H}
                x2={to.x + NODE_W / 2}
                y2={to.y}
                stroke="#4f8cff"
                strokeWidth={2}
                strokeDasharray="4 3"
                markerEnd="url(#arrow)"
              />
            )
          })}
        <defs>
          <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
            <path d="M0,0 L0,6 L6,3 z" fill="#4f8cff" />
          </marker>
        </defs>

        {calls.map((c) => {
          const pos = positions.get(c.call_id)!
          const vendorColor = colorFor(c.vendor_id)
          const isSelected = c.call_id === selectedCallId
          const isAncestor = ancestorIds.has(c.call_id)
          const borderColor =
            c.is_sink && c.decision !== 'ALLOW'
              ? c.decision === 'BLOCK'
                ? 'var(--block)'
                : 'var(--escalate)'
              : vendorColor
          return (
            <g
              key={c.call_id}
              transform={`translate(${pos.x}, ${pos.y})`}
              onClick={() => onSelect(c.call_id)}
              className="graph-node"
            >
              <rect
                width={NODE_W}
                height={NODE_H}
                rx={8}
                fill="var(--panel)"
                stroke={borderColor}
                strokeWidth={isSelected ? 3 : isAncestor ? 2.5 : 1.5}
                opacity={selectedCallId && !isSelected && !isAncestor ? 0.45 : 1}
              />
              <rect x={0} y={0} width={6} height={NODE_H} rx={3} fill={vendorColor} />
              <text x={14} y={20} fontSize={11} fill="var(--text)" fontWeight={600}>
                {c.tool}
              </text>
              <text x={14} y={35} fontSize={10} fill="var(--muted)">
                {c.vendor_id ?? '—'} {c.period ? `· ${c.period}` : ''}
              </text>
              <text x={14} y={48} fontSize={10} fill={c.is_sink ? borderColor : 'var(--muted)'}>
                {c.is_sink ? c.decision : 'graph node'}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}
