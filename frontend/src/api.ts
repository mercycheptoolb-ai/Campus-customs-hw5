import type { Approval, Cash, DecisionResult, EventsResponse, Ticket, TicketSummary } from './types'

/** The FastAPI backend from Problem 7. */
export const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? 'http://localhost:8000'

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  })
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try {
      const body = await res.json()
      msg = body.detail || msg
    } catch {
      /* not json */
    }
    throw new Error(msg)
  }
  return res.json()
}

export const getTickets = () => api<{ tickets: Ticket[] }>('/api/tickets').then((r) => r.tickets)
export const runTicket = (id: number) => api<{ started: boolean }>(`/api/tickets/${id}/run`, { method: 'POST' })
export const getSummary = (id: number) => api<TicketSummary>(`/api/tickets/${id}/summary`)
export const getEvents = (since: number) => api<EventsResponse>(`/api/events?since=${since}&limit=1000`)
export const getApprovals = () => api<{ approvals: Approval[] }>('/api/approvals').then((r) => r.approvals)
export const decide = (id: number, decision: 'approve' | 'reject', approver: string) =>
  api<DecisionResult>(`/api/approvals/${id}/${decision}`, { method: 'POST', body: JSON.stringify({ approver }) })
export const addNote = (id: number, author: string, note: string) =>
  api<{ ok: boolean }>(`/api/tickets/${id}/note`, { method: 'POST', body: JSON.stringify({ author, note }) })
export const getCash = () => api<Cash>('/api/cash')
export const resetDb = () => api<{ reset: boolean }>('/api/reset', { method: 'POST' })
export const getHealth = () => api<{ ok: boolean; model: string; running: boolean }>('/api/health')
