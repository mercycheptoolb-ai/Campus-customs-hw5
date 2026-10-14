import type { AgentName, ToolCall } from './types'

/** How each agent looks and "sounds" on the desk. */
export interface AgentLook {
  name: AgentName
  short: string
  emoji: string
  color: string
  motto: string
  /** CSS class that gives the agent its own voice in bubbles and the wire. */
  voice: string
}

export const AGENTS: Record<AgentName, AgentLook> = {
  Boss: { name: 'Boss', short: 'Boss', emoji: '👑', color: '#ffd166', motto: 'makes the call', voice: 'v-boss' },
  Inventory: { name: 'Inventory', short: 'Inventory', emoji: '📦', color: '#7cc8ff', motto: 'counts every hoodie', voice: 'v-inv' },
  Accounting: { name: 'Accounting', short: 'Accounting', emoji: '💵', color: '#6ee7b7', motto: 'guards the till', voice: 'v-acct' },
  Facilities: { name: 'Facilities', short: 'Facilities', emoji: '🏠', color: '#c4a7ff', motto: 'keeps the lights on', voice: 'v-fac' },
  'Customer Service': { name: 'Customer Service', short: 'Cust. Service', emoji: '💌', color: '#ff8cc4', motto: 'writes the kind notes', voice: 'v-cs' },
}

export const AGENT_ORDER: AgentName[] = ['Boss', 'Inventory', 'Accounting', 'Facilities', 'Customer Service']

export const look = (name?: string): AgentLook => AGENTS[(name as AgentName) ?? 'Boss'] ?? AGENTS.Boss

const QUIET_ARGS = new Set(['requested_by', 'author', 'reason', 'body', 'note', 'resolution', 'task'])

/** check_stock(CC-TEE-WHITE, S, 1) — the short form shown on chips. */
export function fmtCall(call: ToolCall): string {
  if (call.tool === 'delegate') return `delegate → ${String(call.args.to_agent ?? '?')}`
  const vals = Object.entries(call.args)
    .filter(([k, v]) => !QUIET_ARGS.has(k) && v !== null && v !== undefined && v !== '')
    .map(([, v]) => (typeof v === 'string' && v.length > 18 ? v.slice(0, 16) + '…' : String(v)))
  return `${call.tool}(${vals.join(', ')})`
}

export const money = (n: number | null | undefined) =>
  n === null || n === undefined ? '—' : n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })

export const TICKET_TYPE: Record<string, { label: string; icon: string }> = {
  customer_order: { label: 'Customer order', icon: '🛍️' },
  rent_notice: { label: 'Rent notice', icon: '🏠' },
  price_override: { label: 'Discount request', icon: '🏷️' },
}

export const APPROVAL_KIND: Record<string, { label: string; icon: string }> = {
  invoice_payment: { label: 'Pay invoice', icon: '🧾' },
  rent_payment: { label: 'Pay rent', icon: '🏠' },
  purchase_order: { label: 'Purchase order', icon: '📦' },
  price_override: { label: 'Discount sign-off', icon: '🏷️' },
}
