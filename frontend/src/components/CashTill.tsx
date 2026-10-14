import { useEffect, useRef, useState } from 'react'
import { money } from '../agents'
import type { Approval, Cash } from '../types'

/** Animate a number from its last value to the new one (the till "counting out"). */
function useTween(target: number | undefined, ms = 1400) {
  const [value, setValue] = useState(target ?? 0)
  const from = useRef<number | null>(target ?? null)
  useEffect(() => {
    if (target === undefined) return
    if (from.current === null) {
      // first balance we see: show it as-is, only animate real changes
      from.current = target
      setValue(target)
      return
    }
    const start = performance.now()
    const a = from.current
    let raf = 0
    const step = (t: number) => {
      const k = Math.min(1, (t - start) / ms)
      const eased = 1 - Math.pow(1 - k, 3)
      setValue(a + (target - a) * eased)
      if (k < 1) raf = requestAnimationFrame(step)
      else from.current = target
    }
    raf = requestAnimationFrame(step)
    return () => {
      cancelAnimationFrame(raf)
      from.current = target
    }
  }, [target, ms])
  return value
}

export function CashTill({ cash, approvals }: { cash: Cash | null; approvals: Approval[] }) {
  const balance = cash?.balance
  const shown = useTween(balance)
  const prev = useRef<number | undefined>(undefined)
  const [drop, setDrop] = useState<{ amount: number; key: number } | null>(null)

  useEffect(() => {
    if (balance === undefined) return
    if (prev.current !== undefined && balance < prev.current) setDrop({ amount: prev.current - balance, key: Date.now() })
    prev.current = balance
  }, [balance])

  const pending = cash?.pending_approval_amount ?? 0
  const after = cash?.cash_after_pending ?? 0
  const base = Math.max(balance ?? 0, 1)
  const pendingPct = Math.min(100, (pending / base) * 100)
  const receipts = approvals.filter((a) => a.status === 'paid' || a.status === 'refused').slice(-4).reverse()

  return (
    <section className="panel till">
      <div className="panel-head">
        <h2>
          <span className="h-icon">💵</span> The till
        </h2>
        <span className="muted small">checking · as of {cash?.as_of ?? '—'}</span>
      </div>

      <div className={`till-amount ${drop ? 'flash' : ''}`} key={drop?.key}>
        {money(shown)}
        {drop && (
          <span className="till-drop" key={drop.key}>
            −{money(drop.amount)}
          </span>
        )}
      </div>

      <div className="till-bar" title="Pink stripes = money already promised to requests waiting on you">
        <div className="till-bar-pending" style={{ width: `${pendingPct}%` }} />
      </div>
      <div className="till-legend">
        <span>
          <i className="sw sw-pending" /> waiting on you {money(pending)}
        </span>
        <span className={after < 0 ? 'neg' : ''}>
          left after that <b>{money(after)}</b>
        </span>
      </div>
      <p className="till-note">Cash only goes out here — nothing moves until a human approves.</p>

      {receipts.length > 0 && (
        <div className="receipts">
          {receipts.map((r) => (
            <div key={r.id} className={`receipt ${r.status}`}>
              <div className="receipt-row">
                <span>#{r.id} {r.status === 'paid' ? 'PAID' : 'REFUSED'}</span>
                <span>{r.status === 'paid' ? `−${money(r.amount)}` : money(0)}</span>
              </div>
              <div className="receipt-text">{r.result}</div>
              <div className="receipt-sign">signed · {r.decided_by}</div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
