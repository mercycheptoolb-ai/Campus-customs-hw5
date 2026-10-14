import { useCallback, useEffect, useRef, useState } from 'react'
import * as api from '../api'
import type { Approval, Cash, DeskEvent, Ticket, Usage } from '../types'

export interface DeskState {
  tickets: Ticket[]
  approvals: Approval[]
  cash: Cash | null
  events: DeskEvent[]
  running: boolean
  usage: Usage
  online: boolean
  /** Ticket the team is working on right now (from ticket_started without ticket_done). */
  liveTicket: number | null
}

const EMPTY_USAGE: Usage = { requests: 0, input_tokens: 0, output_tokens: 0 }

/** Polls the Problem 7 routes. Faster while the team is working so the floor feels live. */
export function useDesk() {
  const [state, setState] = useState<DeskState>({
    tickets: [],
    approvals: [],
    cash: null,
    events: [],
    running: false,
    usage: EMPTY_USAGE,
    online: true,
    liveTicket: null,
  })
  const since = useRef(0)
  const runId = useRef<number | null>(null)
  const runningRef = useRef(false)

  const refreshShop = useCallback(async () => {
    try {
      const [tickets, approvals, cash] = await Promise.all([api.getTickets(), api.getApprovals(), api.getCash()])
      setState((s) => ({ ...s, tickets, approvals, cash, online: true }))
    } catch {
      setState((s) => ({ ...s, online: false }))
    }
  }, [])

  const pollEvents = useCallback(async () => {
    try {
      let res = await api.getEvents(since.current)
      // New run id (reset / full run) or a restarted backend: start the feed over.
      if ((runId.current !== null && res.run_id !== runId.current) || res.next_since < since.current) {
        since.current = 0
        res = await api.getEvents(0)
        setState((s) => ({ ...s, events: [] }))
      }
      runId.current = res.run_id
      since.current = res.next_since
      runningRef.current = res.running
      setState((s) => {
        const events = res.events.length ? [...s.events, ...res.events] : s.events
        return { ...s, events, running: res.running, usage: res.usage, online: true, liveTicket: res.running ? liveTicketOf(events) : null }
      })
    } catch {
      setState((s) => ({ ...s, online: false }))
    }
  }, [])

  useEffect(() => {
    let alive = true
    let tick = 0
    const loop = async () => {
      if (!alive) return
      await pollEvents()
      if (tick % (runningRef.current ? 2 : 3) === 0) await refreshShop()
      tick += 1
      setTimeout(loop, runningRef.current ? 900 : 2500)
    }
    loop()
    return () => {
      alive = false
    }
  }, [pollEvents, refreshShop])

  const refreshNow = useCallback(async () => {
    await Promise.all([pollEvents(), refreshShop()])
  }, [pollEvents, refreshShop])

  return { ...state, refreshNow }
}

function liveTicketOf(events: DeskEvent[]): number | null {
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i]
    if (e.type === 'ticket_done') return null
    if (e.type === 'ticket_started') return e.ticket_id ?? null
  }
  return null
}
