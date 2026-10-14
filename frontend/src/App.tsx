import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import * as api from './api'
import { money, TICKET_TYPE } from './agents'
import { CashTill } from './components/CashTill'
import { Inbox } from './components/Inbox'
import { RoundTable } from './components/RoundTable'
import { ShiftReport } from './components/ShiftReport'
import { statusLabel, TicketRail } from './components/TicketRail'
import { TopBar } from './components/TopBar'
import { Wire } from './components/Wire'
import { deriveFloor, latestRun } from './floor'
import { useDesk } from './hooks/useDesk'
import type { Approval, TicketSummary } from './types'

type Toast = { id: number; text: string; tone: 'pink' | 'ok' | 'warn' }

export default function App() {
  const desk = useDesk()
  const { tickets, approvals, cash, events, running, liveTicket, refreshNow } = desk
  const [selected, setSelected] = useState<number | null>(() => Number(location.hash.slice(1)) || null)
  const [tab, setTab] = useState<'wire' | 'report'>('wire')
  const [summary, setSummary] = useState<TicketSummary | null>(null)
  const [approver, setApprover] = useState(() => localStorage.getItem('cc-approver') ?? '')
  const [autoHandback, setAutoHandback] = useState(true)
  const [handbackQueue, setHandbackQueue] = useState<number[]>([])
  const [toasts, setToasts] = useState<Toast[]>([])
  const [model, setModel] = useState('gpt-6-luna')
  const [note, setNote] = useState('')

  const toast = useCallback((text: string, tone: Toast['tone'] = 'pink') => {
    const id = Date.now() + Math.random()
    setToasts((t) => [...t, { id, text, tone }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 6000)
  }, [])

  useEffect(() => {
    api.getHealth().then((h) => setModel(h.model)).catch(() => {})
  }, [])
  useEffect(() => localStorage.setItem('cc-approver', approver), [approver])
  useEffect(() => {
    if (tickets.length && (selected === null || !tickets.some((t) => t.id === selected))) setSelected(tickets[0].id)
  }, [tickets, selected])
  useEffect(() => {
    if (selected !== null) history.replaceState(null, '', `#${selected}`)
  }, [selected])

  const ticket = tickets.find((t) => t.id === selected) ?? null
  const run = useMemo(() => (selected === null ? [] : latestRun(events, selected)), [events, selected])
  const floor = useMemo(() => deriveFloor(run), [run])
  const allForTicket = useMemo(() => events.filter((e) => e.ticket_id === selected), [events, selected])
  const live = liveTicket !== null && liveTicket === selected
  const pendingHere = approvals.filter((a) => a.ticket_id === selected && a.status === 'pending')

  // Shift report: refetch when the ticket changes or one of its runs finishes.
  const doneCount = allForTicket.filter((e) => e.type === 'ticket_done').length
  useEffect(() => {
    if (selected === null) return
    api.getSummary(selected).then(setSummary).catch(() => setSummary(null))
  }, [selected, doneCount])

  // Toast + flip to the report when any run finishes; flip to the wire when one starts.
  const lastSeen = useRef(-1)
  useEffect(() => {
    const fresh = events.filter((e) => e.seq > lastSeen.current)
    if (!events.length) return
    if (lastSeen.current >= 0) {
      for (const e of fresh) {
        if (e.type === 'ticket_done') {
          const st = e.final_status ? e.final_status.replace('_', ' ') : e.status
          toast(`#${e.ticket_id} run finished — ${st}`, e.final_status === 'resolved' ? 'ok' : 'pink')
          if (e.ticket_id === selected) setTab('report')
          refreshNow()
        }
        if (e.type === 'ticket_started' && e.ticket_id === selected) setTab('wire')
        if (e.type === 'run_error') toast(`Run stopped: ${e.error ?? 'error'}`, 'warn')
      }
    }
    lastSeen.current = events[events.length - 1].seq
  }, [events, selected, toast, refreshNow])

  const start = useCallback(
    async (id: number, why = 'start') => {
      try {
        await api.runTicket(id)
        setSelected(id)
        setTab('wire')
        toast(why === 'handback' ? `Handing #${id} back to the Boss to close it out` : `The team is on #${id}`)
        await refreshNow()
      } catch (err) {
        toast(String((err as Error).message), 'warn')
      }
    },
    [toast, refreshNow],
  )

  // Hand tickets back to the Boss once the floor is free.
  useEffect(() => {
    if (running || !handbackQueue.length) return
    const [next, ...rest] = handbackQueue
    setHandbackQueue(rest)
    start(next, 'handback')
  }, [running, handbackQueue, start])

  const onDecide = useCallback(
    async (a: Approval, decision: 'approve' | 'reject') => {
      try {
        const r = await api.decide(a.id, decision, approver.trim())
        if (r.status === 'paid') toast(`Paid ${money(a.amount)} — till now ${money(r.checking_balance)}`, 'ok')
        else if (r.status === 'refused') toast(`Pay tool refused #${a.id}: ${r.reason}`, 'warn')
        else toast(`#${a.id} ${r.status}`, 'pink')
        await refreshNow()
        const left = (await api.getApprovals()).filter((x) => x.ticket_id === a.ticket_id && x.status === 'pending')
        const t = tickets.find((x) => x.id === a.ticket_id)
        if (autoHandback && a.ticket_id && !left.length && t && !t.resolved) setHandbackQueue((q) => (q.includes(a.ticket_id!) ? q : [...q, a.ticket_id!]))
      } catch (err) {
        toast(String((err as Error).message), 'warn')
      }
    },
    [approver, autoHandback, tickets, toast, refreshNow],
  )

  const reset = async () => {
    if (!window.confirm('Start a fresh shift? This restores the original database (cash, invoices, tickets) and clears approvals and drafts.')) return
    try {
      await api.resetDb()
      setHandbackQueue([])
      setSummary(null)
      toast('Fresh shift — database restored to the original', 'ok')
      await refreshNow()
    } catch (err) {
      toast(String((err as Error).message), 'warn')
    }
  }

  const type = ticket ? TICKET_TYPE[ticket.type] ?? { label: ticket.type, icon: '🎫' } : null
  const st = ticket ? statusLabel(ticket, live, pendingHere.length) : null
  const queued = ticket ? handbackQueue.includes(ticket.id) : false
  let action: { label: string; disabled: boolean; hint: string } | null = null
  if (ticket) {
    if (ticket.resolved) action = { label: '✓ Resolved', disabled: true, hint: 'The Boss closed this ticket.' }
    else if (live) action = { label: 'Team is working…', disabled: true, hint: 'Watch the table and the wire.' }
    else if (pendingHere.length) action = { label: `Waiting on your signature (${pendingHere.length})`, disabled: true, hint: 'Sign or reject the requests on the right — then the Boss closes it out.' }
    else if (running) action = { label: queued ? 'Queued for the Boss' : 'Floor busy', disabled: true, hint: 'One ticket at a time — cash is shared.' }
    else if (ticket.status === 'open') action = { label: '▶ Put the team on it', disabled: false, hint: 'The Boss reads it and calls only who it needs.' }
    else action = { label: '↻ Hand back to the Boss', disabled: false, hint: 'The Boss picks it up from the log and closes it out.' }
  }

  return (
    <div className="app">
      <TopBar
        shopToday={cash?.shop_today}
        model={model}
        usage={desk.usage}
        online={desk.online}
        running={running}
        approver={approver}
        onApprover={setApprover}
        onReset={reset}
      />

      <div className="desk">
        <TicketRail tickets={tickets} approvals={approvals} selected={selected} liveTicket={liveTicket} onSelect={setSelected} />

        <main className="center">
          {ticket && type && st && action ? (
            <>
              <section className="ticket-header panel">
                <div className="th-left">
                  <div className="eyebrow">
                    {type.icon} {type.label} · from {ticket.requester}
                  </div>
                  <h1>
                    <span className="hash">#{ticket.id}</span> {ticket.subject}
                  </h1>
                  {ticket.notes && <p className="th-notes">“{ticket.notes}”</p>}
                </div>
                <div className="th-right">
                  <span className={`pill big ${st.cls}`}>{st.text}</span>
                  <button className={`btn primary big ${live ? 'pulsing' : ''}`} disabled={action.disabled} onClick={() => start(ticket.id, ticket.status === 'open' ? 'start' : 'handback')}>
                    {action.label}
                  </button>
                  <span className="muted small">{action.hint}</span>
                </div>
                {ticket.resolved && <div className="stamp big">RESOLVED</div>}
                {!ticket.resolved && !live && ticket.status !== 'open' && (
                  <form
                    className="boss-note"
                    onSubmit={async (e) => {
                      e.preventDefault()
                      if (!approver.trim()) return toast('Type your name in “on desk” first', 'warn')
                      try {
                        await api.addNote(ticket.id, approver.trim(), note)
                        setNote('')
                        toast('Note left for the Boss — hand the ticket back to act on it', 'ok')
                        await refreshNow()
                      } catch (err) {
                        toast(String((err as Error).message), 'warn')
                      }
                    }}
                  >
                    <span className="eyebrow">✍️ note to the Boss</span>
                    <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Your call on this ticket, e.g. “fill the 8 in stock, decline the rest”" maxLength={1000} />
                    <button className="btn ghost small" disabled={!note.trim()}>
                      Leave note
                    </button>
                  </form>
                )}
              </section>

              <section className="panel floor-panel">
                <RoundTable floor={floor} ticketId={ticket.id} live={live} hasRun={run.length > 0} />
              </section>

              <section className="panel log-panel">
                <div className="tabs">
                  <button className={tab === 'wire' ? 'on' : ''} onClick={() => setTab('wire')}>
                    Live wire <span className="muted">· what everyone is saying</span>
                  </button>
                  <button className={tab === 'report' ? 'on' : ''} onClick={() => setTab('report')}>
                    Shift report <span className="muted">· what each agent did</span>
                  </button>
                  <label className="auto">
                    <input type="checkbox" checked={autoHandback} onChange={(e) => setAutoHandback(e.target.checked)} /> hand back to the Boss after I sign
                  </label>
                </div>
                {tab === 'wire' ? <Wire events={allForTicket} live={live} /> : <ShiftReport summary={summary} />}
              </section>
            </>
          ) : (
            <section className="panel empty big-empty">{desk.online ? 'Loading the ticket spike…' : 'Waiting for the backend at http://localhost:8000 …'}</section>
          )}
        </main>

        <aside className="side">
          <CashTill cash={cash} approvals={approvals} />
          <Inbox approvals={approvals} selected={selected} approver={approver} onDecide={onDecide} />
        </aside>
      </div>

      <div className="toasts">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.tone}`}>
            {t.text}
          </div>
        ))}
      </div>
    </div>
  )
}
