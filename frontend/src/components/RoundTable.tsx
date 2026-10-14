import { AGENT_ORDER, look } from '../agents'
import type { Floor, SeatState } from '../floor'
import type { AgentName } from '../types'

// Where each agent sits around the table (percent of the floor box). The Boss sits at the head.
const SEATS: Record<AgentName, { x: number; y: number; bubble: 'right' | 'above-l' | 'above-r' | 'below' }> = {
  Boss: { x: 50, y: 11, bubble: 'right' },
  Inventory: { x: 12, y: 44, bubble: 'above-l' },
  Accounting: { x: 88, y: 44, bubble: 'above-r' },
  Facilities: { x: 27, y: 70, bubble: 'below' },
  'Customer Service': { x: 73, y: 70, bubble: 'below' },
}
const CENTER = { x: 50, y: 50 }

const STATE_TEXT: Record<SeatState, string> = {
  idle: 'off duty',
  thinking: 'thinking',
  tool: 'checking the books',
  waiting: 'waiting on',
  done: 'done',
}

function curve(a: AgentName, b: AgentName) {
  const p = SEATS[a]
  const q = SEATS[b]
  const cx = (p.x + q.x) / 2 + (CENTER.x - (p.x + q.x) / 2) * 0.55
  const cy = (p.y + q.y) / 2 + (CENTER.y - (p.y + q.y) / 2) * 0.55
  return { d: `M ${p.x} ${p.y} Q ${cx} ${cy} ${q.x} ${q.y}`, mx: (p.x + 2 * cx + q.x) / 4, my: (p.y + 2 * cy + q.y) / 4 }
}

interface Props {
  floor: Floor
  ticketId: number
  live: boolean
  hasRun: boolean
}

export function RoundTable({ floor, ticketId, live, hasRun }: Props) {
  const delegations = floor.links.reduce((n, l) => n + l.count, 0)
  return (
    <div className="floor">
      <svg className="floor-lines" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden>
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--pink)" />
          </marker>
        </defs>
        {floor.links.map((l) => {
          const c = curve(l.from, l.to)
          return (
            <path
              key={`${l.from}>${l.to}`}
              d={c.d}
              className={`link ${l.active > 0 ? 'active' : ''}`}
              vectorEffect="non-scaling-stroke"
              markerEnd="url(#arrow)"
              style={{ ['--c' as string]: look(l.from).color }}
            />
          )
        })}
      </svg>
      {floor.links.map((l) => {
        const c = curve(l.from, l.to)
        return l.count > 1 ? (
          <span key={`n-${l.from}>${l.to}`} className="link-count" style={{ left: `${c.mx}%`, top: `${c.my}%` }}>
            ×{l.count}
          </span>
        ) : null
      })}

      <div className={`table ${live ? 'live' : ''}`}>
        <div className="table-num">#{ticketId}</div>
        <div className="table-state">{live ? 'team is on it' : floor.finished ? 'run finished' : hasRun ? 'paused' : 'nobody at the table yet'}</div>
        {delegations > 0 && (
          <div className="table-meta">
            {delegations} handoff{delegations === 1 ? '' : 's'}
          </div>
        )}
      </div>

      {AGENT_ORDER.map((name) => {
        const seat = floor.seats[name]
        const pos = SEATS[name]
        const lk = look(name)
        const speaking = seat.state !== 'idle' && seat.state !== 'done'
        return (
          <div
            key={name}
            className={`seat s-${seat.state} ${seat.touched ? 'touched' : hasRun ? 'untouched' : 'waiting-room'}`}
            style={{ left: `${pos.x}%`, top: `${pos.y}%`, ['--c' as string]: lk.color }}
          >
            <div className="avatar">
              <span>{lk.emoji}</span>
              {speaking && <i className="ring" />}
            </div>
            <div className="seat-name">{lk.short}</div>
            <div className="seat-state">
              {STATE_TEXT[seat.state]}
              {seat.state === 'waiting' && seat.waitingOn ? ` ${seat.waitingOn}` : ''}
              {seat.toolCount > 0 && <span className="seat-tools"> · {seat.toolCount} tool calls</span>}
            </div>
            {seat.line && (
              <div className={`bubble b-${pos.bubble} ${lk.voice} ${speaking ? 'speaking' : ''}`}>
                <div className="bubble-text">{seat.line}</div>
                {seat.lastTools.length > 0 && speaking && (
                  <div className="bubble-tools">
                    {seat.lastTools.slice(0, 3).map((t, i) => (
                      <code key={i}>{t}</code>
                    ))}
                  </div>
                )}
              </div>
            )}
            {!seat.touched && hasRun && <div className="seat-off">not needed</div>}
          </div>
        )
      })}
    </div>
  )
}
