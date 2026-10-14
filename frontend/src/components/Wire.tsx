import { useEffect, useRef } from 'react'
import { fmtCall, look } from '../agents'
import type { DeskEvent } from '../types'

function Who({ name }: { name?: string }) {
  const lk = look(name)
  return (
    <span className="who" style={{ ['--c' as string]: lk.color }}>
      <span className="who-dot">{lk.emoji}</span>
      {lk.name}
    </span>
  )
}

const time = (ts: number) => new Date(ts * 1000).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', second: '2-digit' })

export function Wire({ events, live }: { events: DeskEvent[]; live: boolean }) {
  const box = useRef<HTMLDivElement>(null)
  const pinned = useRef(true)

  useEffect(() => {
    const el = box.current
    if (el && pinned.current) el.scrollTop = el.scrollHeight
  }, [events.length])

  const rows = events.filter((e) => ['agent_said', 'tool_results', 'delegation_started', 'delegation_done', 'ticket_started', 'ticket_done', 'human_note', 'approval_decided'].includes(e.type))

  return (
    <div
      className="wire"
      ref={box}
      onScroll={(e) => {
        const el = e.currentTarget
        pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 60
      }}
    >
      {rows.length === 0 && <div className="empty">The wire is quiet. Start the team and every message, tool call, and handoff shows up here.</div>}
      {rows.map((e) => {
        switch (e.type) {
          case 'ticket_started':
            return (
              <div key={e.seq} className="wire-divider">
                <span>run started · {time(e.ts)}</span>
              </div>
            )
          case 'ticket_done':
            return (
              <div key={e.seq} className="wire-divider done">
                <span>
                  run finished · {e.final_status ? e.final_status.replace('_', ' ') : e.status} · {time(e.ts)}
                </span>
              </div>
            )
          case 'human_note':
            return (
              <div key={e.seq} className="wire-human">
                <b>✍️ {String(e.author)}</b> left a note for the Boss: “{String(e.note)}”
              </div>
            )
          case 'approval_decided':
            return null
          case 'delegation_started':
            return (
              <div key={e.seq} className="wire-handoff" style={{ ['--c' as string]: look(e.agent).color }}>
                <div className="handoff-route">
                  <Who name={e.agent} /> <span className="arrow">→</span> <Who name={e.to_agent} />
                </div>
                <div className="handoff-task">“{e.said}”</div>
              </div>
            )
          case 'delegation_done':
            return (
              <div key={e.seq} className="wire-reply" style={{ ['--c' as string]: look(e.agent).color }}>
                <div className="handoff-route">
                  <Who name={e.agent} /> <span className="arrow">↩</span> <Who name={e.to_agent} />
                  {e.status === 'error' && <span className="pill blocked">error</span>}
                </div>
                <div className="reply-text">{(e.said ?? '').split('\n')[0]}</div>
              </div>
            )
          case 'tool_results': {
            const results = e.results ?? []
            if (!results.length && !(e.retries ?? []).length) return null
            return (
              <details key={e.seq} className="wire-results">
                <summary>
                  ↳ {results.map((r) => r.tool).join(', ')} answered{(e.retries ?? []).length ? ` · ${(e.retries ?? []).length} retry` : ''}
                </summary>
                {results.map((r, i) => (
                  <pre key={i}>
                    <b>{r.tool}</b> {r.content}
                  </pre>
                ))}
                {(e.retries ?? []).map((r, i) => (
                  <pre key={`r${i}`} className="retry">
                    {r}
                  </pre>
                ))}
              </details>
            )
          }
          default: {
            const tools = (e.tools ?? []).filter((t) => t.tool !== 'delegate')
            if (!e.said && !tools.length) return null
            const lk = look(e.agent)
            return (
              <div key={e.seq} className={`wire-msg ${lk.voice} ${e.final ? 'final' : ''}`} style={{ ['--c' as string]: lk.color }}>
                <div className="msg-head">
                  <Who name={e.agent} />
                  {e.final && <span className="pill report-tag">report</span>}
                  <span className="msg-time">{time(e.ts)}</span>
                </div>
                {e.said && <div className="msg-text">{e.said}</div>}
                {tools.length > 0 && (
                  <div className="msg-tools">
                    {tools.map((t, i) => (
                      <code key={i} title={JSON.stringify(t.args, null, 1)}>
                        🔧 {fmtCall(t)}
                      </code>
                    ))}
                  </div>
                )}
              </div>
            )
          }
        }
      })}
      {live && (
        <div className="typing">
          <span />
          <span />
          <span />
        </div>
      )}
    </div>
  )
}
