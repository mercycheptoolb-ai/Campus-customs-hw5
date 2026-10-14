import { TICKET_TYPE } from '../agents'
import type { Approval, Ticket } from '../types'

export function statusLabel(t: Ticket, live: boolean, pending: number): { text: string; cls: string } {
  if (live) return { text: 'team on it', cls: 'live' }
  if (t.status === 'resolved') return { text: 'resolved', cls: 'resolved' }
  if (pending > 0) return { text: `needs you · ${pending}`, cls: 'needs' }
  switch (t.status) {
    case 'awaiting_approval':
      return { text: 'back to the Boss', cls: 'handback' }
    case 'blocked':
      return { text: 'blocked', cls: 'blocked' }
    case 'in_progress':
      return { text: 'in progress', cls: 'progress' }
    default:
      return { text: 'open', cls: 'open' }
  }
}

interface Props {
  tickets: Ticket[]
  approvals: Approval[]
  selected: number | null
  liveTicket: number | null
  onSelect: (id: number) => void
}

export function TicketRail({ tickets, approvals, selected, liveTicket, onSelect }: Props) {
  const resolved = tickets.filter((t) => t.resolved).length
  return (
    <aside className="rail">
      <div className="rail-head">
        <h2>Ticket spike</h2>
        <span className="muted small">
          {resolved}/{tickets.length} resolved
        </span>
      </div>
      <div className="rail-progress">
        <div style={{ width: `${tickets.length ? (resolved / tickets.length) * 100 : 0}%` }} />
      </div>

      {tickets.map((t, i) => {
        const pending = approvals.filter((a) => a.ticket_id === t.id && a.status === 'pending').length
        const st = statusLabel(t, liveTicket === t.id, pending)
        const type = TICKET_TYPE[t.type] ?? { label: t.type, icon: '🎫' }
        const facts = [t.sku, t.size && `size ${t.size}`, t.qty && `×${t.qty}`, t.invoice_id && `inv ${t.invoice_id}`, t.lease_id && `lease ${t.lease_id}`]
          .filter(Boolean)
          .join(' · ')
        return (
          <button
            key={t.id}
            className={`ticket ${selected === t.id ? 'selected' : ''} ${st.cls}`}
            style={{ ['--tilt' as string]: `${[-1.2, 0.8, -0.5][i % 3]}deg` }}
            onClick={() => onSelect(t.id)}
          >
            <div className="ticket-top">
              <span className="ticket-num">#{t.id}</span>
              <span className={`pill ${st.cls}`}>{st.text}</span>
            </div>
            <div className="ticket-type">
              {type.icon} {type.label}
            </div>
            <div className="ticket-subject">{t.subject}</div>
            <div className="ticket-from">from {t.requester}</div>
            {facts && <div className="ticket-facts">{facts}</div>}
            {t.resolved && <div className="stamp">RESOLVED</div>}
          </button>
        )
      })}
      <p className="rail-foot muted small">Pick a ticket, then put the team on it.</p>
    </aside>
  )
}
