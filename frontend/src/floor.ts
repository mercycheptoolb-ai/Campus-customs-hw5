import { AGENT_ORDER, fmtCall } from './agents'
import type { AgentName, DeskEvent } from './types'

export type SeatState = 'idle' | 'thinking' | 'tool' | 'waiting' | 'done'

export interface Seat {
  agent: AgentName
  state: SeatState
  line: string
  lastTools: string[]
  toolCount: number
  waitingOn?: AgentName
  active: number
  touched: boolean
}

export interface Link {
  from: AgentName
  to: AgentName
  active: number
  count: number
}

export interface Floor {
  seats: Record<AgentName, Seat>
  links: Link[]
  finished: boolean
}

/** Events for one ticket, from its latest ticket_started onwards (the current or last run). */
export function latestRun(events: DeskEvent[], ticketId: number): DeskEvent[] {
  const mine = events.filter((e) => e.ticket_id === ticketId)
  let start = 0
  for (let i = mine.length - 1; i >= 0; i--) {
    if (mine[i].type === 'ticket_started') {
      start = i
      break
    }
  }
  return mine.slice(start)
}

const firstSentence = (s: string, max = 170) => {
  const one = s.split('\n')[0]
  return one.length > max ? one.slice(0, max - 1) + '…' : one
}

/** Replay a run's events into who is doing what around the table. */
export function deriveFloor(run: DeskEvent[]): Floor {
  const seats = Object.fromEntries(
    AGENT_ORDER.map((a) => [a, { agent: a, state: 'idle', line: '', lastTools: [], toolCount: 0, active: 0, touched: false } as Seat]),
  ) as Record<AgentName, Seat>
  const links = new Map<string, Link>()
  let finished = false

  for (const e of run) {
    const seat = e.agent ? seats[e.agent] : undefined
    switch (e.type) {
      case 'agent_started':
        if (!seat) break
        seat.active += 1
        seat.touched = true
        seat.state = 'thinking'
        if (!seat.line) seat.line = 'Reading the brief…'
        break
      case 'agent_said': {
        if (!seat) break
        const tools = (e.tools ?? []).filter((t) => t.tool !== 'delegate')
        if (tools.length) {
          seat.state = 'tool'
          seat.lastTools = tools.map(fmtCall)
          seat.toolCount += tools.length
          seat.line = e.said ? firstSentence(e.said) : `Checking ${tools.map((t) => t.tool).join(', ')}…`
        } else if (e.said) {
          seat.line = firstSentence(e.said)
          seat.state = e.final ? 'done' : 'thinking'
        }
        break
      }
      case 'delegation_started': {
        if (!e.agent || !e.to_agent) break
        const key = `${e.agent}>${e.to_agent}`
        const link = links.get(key) ?? { from: e.agent, to: e.to_agent, active: 0, count: 0 }
        link.active += 1
        link.count += 1
        links.set(key, link)
        seats[e.agent].state = 'waiting'
        seats[e.agent].waitingOn = e.to_agent
        seats[e.agent].line = `Asking ${e.to_agent}: ${firstSentence(e.said ?? '', 120)}`
        break
      }
      case 'delegation_done': {
        // agent = the helper who answered, to_agent = the agent who asked
        if (!e.agent || !e.to_agent) break
        const link = links.get(`${e.to_agent}>${e.agent}`)
        if (link) link.active = Math.max(0, link.active - 1)
        const asker = seats[e.to_agent]
        if (![...links.values()].some((l) => l.from === e.to_agent && l.active > 0)) {
          asker.state = 'thinking'
          asker.waitingOn = undefined
        }
        break
      }
      case 'agent_done':
        if (!seat) break
        seat.active = Math.max(0, seat.active - 1)
        if (seat.active === 0) seat.state = 'done'
        if (e.said) seat.line = firstSentence(e.said)
        break
      case 'ticket_done':
        finished = true
        break
    }
  }
  if (finished) for (const s of Object.values(seats)) if (s.touched) s.state = 'done'
  return { seats, links: [...links.values()], finished }
}
