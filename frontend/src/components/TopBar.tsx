import type { Usage } from '../types'

interface Props {
  shopToday?: string
  model: string
  usage: Usage
  online: boolean
  running: boolean
  approver: string
  onApprover: (name: string) => void
  onReset: () => void
}

export function TopBar({ shopToday, model, usage, online, running, approver, onApprover, onReset }: Props) {
  const d = shopToday ? new Date(shopToday + 'T12:00:00') : null
  return (
    <header className="topbar">
      <div className="brand">
        <div className="logo" aria-hidden>
          🐶
        </div>
        <div>
          <div className="brand-name">
            Campus Customs <span className="brand-sub">Ops Desk</span>
          </div>
          <div className="brand-tag">five agents, one register, and you holding the pen</div>
        </div>
      </div>

      {d && (
        <div className="calendar" title="Shop 'today' comes from desk.date_today, not the wall clock">
          <div className="cal-month">{d.toLocaleDateString('en-US', { month: 'short' }).toUpperCase()}</div>
          <div className="cal-day">{d.getDate()}</div>
          <div className="cal-week">{d.toLocaleDateString('en-US', { weekday: 'short' })} · shop day</div>
        </div>
      )}

      <div className="topbar-right">
        <div className="meter" title="Tokens this shift (since the last reset)">
          <span className="meter-label">tokens this shift</span>
          <span className="meter-value">
            {(usage.input_tokens / 1000).toFixed(1)}k in · {(usage.output_tokens / 1000).toFixed(1)}k out
          </span>
        </div>
        <span className="chip model-chip" title="Every agent runs on this one model through Portkey">
          {model}
        </span>
        <label className="signin" title="Your name goes on every approval. Agents can't sign.">
          <span>on desk</span>
          <input value={approver} placeholder="your name" maxLength={40} onChange={(e) => onApprover(e.target.value)} />
        </label>
        <span className={`status-dot ${online ? (running ? 'busy' : 'on') : 'off'}`} title={online ? 'Backend connected' : 'Backend offline'}>
          {online ? (running ? 'team working' : 'connected') : 'backend offline'}
        </span>
        <button className="btn ghost small" onClick={onReset} disabled={running} title="Restore the original database">
          ↺ Fresh shift
        </button>
      </div>
    </header>
  )
}
