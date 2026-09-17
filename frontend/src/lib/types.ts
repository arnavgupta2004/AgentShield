export type Decision = 'ALLOW' | 'BLOCK' | 'ESCALATE'

export interface FixtureSummary {
  session_id: string
  category: string
  expected_label: 'ALLOW' | 'BLOCK'
  expected_conflict_class: string | null
  num_calls: number
}

export interface FixtureCall {
  tool: string
  resource_id: string | null
  vendor_id: string | null
  period: string | null
  provenance: string | null
  recipient: string | null
  payload_refs: string[]
  params: Record<string, unknown>
}

export interface FixtureDetail {
  session_id: string
  category: string
  expected_label: 'ALLOW' | 'BLOCK'
  expected_conflict_class: string | null
  calls: FixtureCall[]
}

export interface EvaluateResponse {
  session_id: string
  final_decision: Decision
  matched_conflict_class: string | null
  traces: Trace[]
}

export interface ConflictClassMatch {
  conflict_class: string
  member_compartments_involved: string[]
  actual_count: number
  clearance_threshold: number
  margin: number
  verdict: Decision
}

export interface Trace {
  call_id: string
  session_id: string
  tool: string
  recipient: string | null
  decision: Decision
  matched_conflict_class: string | null
  ancestor_call_ids: string[]
  matches: ConflictClassMatch[]
}

export interface CallEvent {
  type: 'call'
  call_id: string
  tool: string
  resource_id: string | null
  vendor_id: string | null
  period: string | null
  recipient: string | null
  is_sink: boolean
  compartment_tags: Record<string, string>
  decision: Decision
  trace: Trace | null
}

export interface SessionStartEvent {
  type: 'session_start'
  session_id: string
  system: string
  policy_variant: string
  expected_label: Decision | null
  expected_conflict_class: string | null
}

export interface SessionCompleteEvent {
  type: 'session_complete'
  session_id: string
  system: string
  final_decision: Decision
}

export interface ErrorEvent {
  type: 'error'
  message: string
}

export type StreamEvent = SessionStartEvent | CallEvent | SessionCompleteEvent | ErrorEvent

export interface BenchmarkRow {
  session_id: string
  category: string
  expected_label: 'ALLOW' | 'BLOCK'
  expected_conflict_class: string | null
  system: string
  actual_decision: Decision
  matched_conflict_class: string | null
  passed: boolean
}

export interface SystemMetrics {
  tp: number
  fp: number
  tn: number
  fn: number
  precision: number
  recall: number
  f1: number
}

export interface BenchmarkResults {
  total_sessions: number
  rows: BenchmarkRow[]
  metrics: Record<string, SystemMetrics>
  false_positive_rate_benign_subset: Record<string, number>
  attack_breakdown: Record<string, string>
}
