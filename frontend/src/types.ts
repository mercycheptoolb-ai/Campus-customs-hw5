export type AgentName = 'Boss' | 'Inventory' | 'Accounting' | 'Facilities' | 'Customer Service'

export type TicketStatus = 'open' | 'in_progress' | 'awaiting_approval' | 'blocked' | 'resolved'

/** GET /api/tickets */
export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  status: TicketStatus
  resolved: boolean
  state: 'open' | 'resolved'
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  notes: string | null
}

/** GET /api/approvals */
export interface Approval {
  id: number
  ticket_id: number | null
  kind: 'invoice_payment' | 'rent_payment' | 'purchase_order' | 'price_override'
  ref_id: number | null
  amount: number
  summary: string
  details: string | null
  requested_by: AgentName
  status: 'pending' | 'approved' | 'rejected' | 'paid' | 'refused'
  decided_by: string | null
  decided_at: string | null
  result: string | null
  created_at: string
}

/** GET /api/cash */
export interface Cash {
  account: string
  balance: number
  as_of: string
  shop_today: string
  pending_approval_amount: number
  cash_after_pending: number
}

export interface ToolCall {
  tool: string
  args: Record<string, unknown>
}

/** One item from GET /api/events (flattened by the backend). */
export interface DeskEvent {
  seq: number
  run_id: number
  ts: number
  type:
    | 'agent_said'
    | 'tool_results'
    | 'agent_started'
    | 'agent_done'
    | 'delegation_started'
    | 'delegation_done'
    | 'ticket_started'
    | 'ticket_done'
    | 'run_started'
    | 'run_done'
    | 'run_error'
    | 'approval_decided'
    | 'db_reset'
    | string
  ticket_id?: number
  agent?: AgentName
  to_agent?: AgentName
  said?: string
  final?: boolean
  tools?: ToolCall[]
  results?: { tool: string; content: string }[]
  retries?: string[]
  status?: string
  delegation_id?: number
  chain?: AgentName[]
  summary?: string
  final_status?: TicketStatus | null
  model?: string
  tokens?: { in: number; out: number }
  error?: string
  [key: string]: unknown
}

export interface Usage {
  requests: number
  input_tokens: number
  output_tokens: number
}

export interface EventsResponse {
  run_id: number
  running: boolean
  next_since: number
  usage: Usage
  events: DeskEvent[]
}

export interface AgentReport {
  ticket_id: number
  findings: string[]
  actions_taken: string[]
  blockers: string[]
  summary: string
}

export interface BossDecision {
  ticket_id: number
  final_status: TicketStatus
  delegated_to: AgentName[]
  decision: string
  human_actions: string[]
}

export interface Draft {
  id: number
  ticket_id: number
  recipient: string
  subject: string
  body: string
  author: string
  status: string
}

/** GET /api/tickets/{id}/summary */
export interface TicketSummary {
  ticket_id: number
  run_id: string | null
  finished?: boolean
  boss: BossDecision | null
  agents: {
    agent: AgentName
    runs: number
    tools: Record<string, number>
    asked_by: AgentName[]
    delegated_to: AgentName[]
    reports: AgentReport[]
  }[]
  drafts: Draft[]
}

export interface DecisionResult {
  ok?: boolean
  status?: string
  result?: string
  reason?: string
  checking_balance?: number
}
