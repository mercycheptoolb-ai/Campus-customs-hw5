import { look } from '../agents'
import type { TicketSummary } from '../types'

export function ShiftReport({ summary }: { summary: TicketSummary | null }) {
  if (!summary || !summary.run_id) {
    return <div className="empty">No shift report yet. Once the team has worked this ticket, each agent's summary lands here.</div>
  }
  const boss = summary.boss
  return (
    <div className="report">
      {boss && (
        <div className="boss-call">
          <div className="boss-call-head">
            <span className="who-dot big">👑</span>
            <div>
              <div className="eyebrow">The Boss's call</div>
              <span className={`pill st-${boss.final_status}`}>{boss.final_status.replace('_', ' ')}</span>
            </div>
          </div>
          <p className="boss-decision">{boss.decision}</p>
          {boss.human_actions.length > 0 && (
            <ul className="todo">
              {boss.human_actions.map((a, i) => (
                <li key={i}>☐ {a}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="report-grid">
        {summary.agents
          .filter((a) => a.agent !== 'Boss')
          .map((a) => {
            const lk = look(a.agent)
            const last = a.reports[a.reports.length - 1]
            const actions = [...new Set(a.reports.flatMap((r) => r.actions_taken))]
            const blockers = [...new Set(a.reports.flatMap((r) => r.blockers))]
            return (
              <article key={a.agent} className={`report-card ${lk.voice}`} style={{ ['--c' as string]: lk.color }}>
                <header>
                  <span className="who-dot">{lk.emoji}</span>
                  <div>
                    <div className="report-name">{lk.name}</div>
                    <div className="muted small">
                      asked by {[...new Set(a.asked_by)].join(', ') || '—'}
                      {a.runs > 1 ? ` · ${a.runs} times` : ''}
                    </div>
                  </div>
                </header>
                <p className="report-summary">{last?.summary ?? 'Still working…'}</p>
                {actions.length > 0 && (
                  <ul className="report-list did">
                    {actions.slice(0, 4).map((x, i) => (
                      <li key={i}>{x}</li>
                    ))}
                  </ul>
                )}
                {blockers.length > 0 && (
                  <ul className="report-list blocked">
                    {blockers.slice(0, 3).map((x, i) => (
                      <li key={i}>{x}</li>
                    ))}
                  </ul>
                )}
                <div className="report-tools">
                  {Object.entries(a.tools).map(([t, n]) => (
                    <code key={t}>
                      {t}
                      {n > 1 ? ` ×${n}` : ''}
                    </code>
                  ))}
                  {a.delegated_to.length > 0 && <code className="deleg">→ {[...new Set(a.delegated_to)].join(', ')}</code>}
                </div>
              </article>
            )
          })}
      </div>

      {summary.drafts.length > 0 && (
        <div className="drafts">
          {summary.drafts.map((d) => (
            <div key={d.id} className="letter">
              <div className="letter-head">
                <span>💌 Draft #{d.id} to {d.recipient}</span>
                <span className="pill open">not sent · stays on the board</span>
              </div>
              <div className="letter-subject">{d.subject}</div>
              <div className="letter-body">{d.body}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
