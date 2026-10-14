import { useState } from 'react'
import { APPROVAL_KIND, look, money } from '../agents'
import type { Approval } from '../types'

interface Props {
  approvals: Approval[]
  selected: number | null
  approver: string
  onDecide: (a: Approval, decision: 'approve' | 'reject') => Promise<void>
}

/** Rule hints the human should see before signing. */
function warning(a: Approval, all: Approval[]): string | null {
  if (a.kind === 'purchase_order' && a.details?.includes('BLOCKED')) {
    const inv = all.find((x) => x.kind === 'invoice_payment' && x.status === 'pending')
    return `Vendor won't ship until its open invoice is paid${inv ? ` — approve #${inv.id} first` : ''}, or the pay tool will refuse this.`
  }
  return null
}

export function Inbox({ approvals, selected, approver, onDecide }: Props) {
  const [busy, setBusy] = useState<number | null>(null)
  const pending = approvals.filter((a) => a.status === 'pending').sort((a, b) => Number(b.ticket_id === selected) - Number(a.ticket_id === selected) || a.id - b.id)
  const decided = approvals.filter((a) => a.status !== 'pending').slice(-3).reverse()
  const signed = approver.trim().length > 0

  return (
    <section className="panel inbox">
      <div className="panel-head">
        <h2>
          <span className="h-icon">✍️</span> Needs your signature
        </h2>
        {pending.length > 0 && <span className="count-badge">{pending.length}</span>}
      </div>
      {!signed && pending.length > 0 && <div className="nudge">Type your name in “on desk” up top to sign. Agents prepare — only a human approves.</div>}

      {pending.length === 0 && <div className="empty small">Nothing to sign. When an agent prepares a payment, purchase order, or discount, it waits here for you.</div>}

      {pending.map((a) => {
        const k = APPROVAL_KIND[a.kind]
        const lk = look(a.requested_by)
        const warn = warning(a, approvals)
        return (
          <div key={a.id} className={`slip ${a.ticket_id === selected ? 'mine' : ''}`}>
            <div className="slip-top">
              <span className="slip-kind">
                {k.icon} {k.label}
              </span>
              <span className="slip-ticket">ticket #{a.ticket_id} · req #{a.id}</span>
            </div>
            <div className="slip-amount">{a.kind === 'price_override' ? 'price sign-off' : money(a.amount)}</div>
            <div className="slip-summary">{a.summary}</div>
            {a.details && <div className="slip-details">{a.details}</div>}
            {warn && <div className="slip-warn">⚠ {warn}</div>}
            <div className="slip-from" style={{ ['--c' as string]: lk.color }}>
              prepared by <b>{lk.emoji} {lk.name}</b>
            </div>
            <div className="slip-actions">
              <button
                className="btn primary"
                disabled={!signed || busy !== null}
                onClick={async () => {
                  setBusy(a.id)
                  await onDecide(a, 'approve')
                  setBusy(null)
                }}
              >
                {busy === a.id ? 'Signing…' : a.kind === 'price_override' ? 'Approve price' : `Approve & pay ${money(a.amount)}`}
              </button>
              <button
                className="btn ghost"
                disabled={!signed || busy !== null}
                onClick={async () => {
                  setBusy(a.id)
                  await onDecide(a, 'reject')
                  setBusy(null)
                }}
              >
                Reject
              </button>
            </div>
          </div>
        )
      })}

      {decided.length > 0 && (
        <div className="decided">
          <div className="eyebrow">recently decided</div>
          {decided.map((a) => (
            <div key={a.id} className={`decided-row ${a.status}`}>
              <span>
                {APPROVAL_KIND[a.kind].icon} #{a.id} {a.summary.split(' — ')[0]}
              </span>
              <span className={`pill st-${a.status}`}>{a.status}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
