# Campus Customs Ops Desk — design notes

The dashboard (`frontend/`, React + Vite + TypeScript) is meant to feel like **the counter of a small campus shop after closing**. Tickets hang on a spike, the team sits around a table, the till is in the corner, and you hold the pen. It runs on `npm run dev` at http://localhost:5173 and talks to the FastAPI backend at http://localhost:8000. The backend's CORS allows exactly `http://localhost:5173` and `http://127.0.0.1:5173`.

The palette is black and pink, per the project rules. Near-black "felt" with a faint dot grid and two soft pink glows makes the screen feel like a lit desk rather than an admin panel. Pink is reserved for **things that are alive or need you**: the running ticket, active handoffs, the approve button, money leaving.

---

## Layout: three zones, read left to right

| Zone | What it is | Why |
|---|---|---|
| **Left: the ticket spike** | The three tickets as cream paper receipts with a perforated edge, each tilted slightly differently, and a progress bar (*1/3 resolved*) on top | Tickets are physical things in a shop. Paper against black makes them the brightest, most "grab-able" objects, and the tilt makes them feel pinned up by hand rather than rendered. The selected ticket straightens and slides out with a pink outline |
| **Centre: the floor** | The ticket header, then **the round table** with the five agents seated around it, then a tabbed **Live wire / Shift report** | This is where the work happens, so it gets the most space. The table answers "who is working on this right now?" at a glance; the wire answers "what exactly did they say and do?" |
| **Right: the money side** | **The till** (checking balance) above **Needs your signature** (approvals) | Money and the human's job sit together, and are always visible no matter which ticket is open. That's where your eye goes when you're asked to sign |

The top bar carries the brand, a tear-off **paper calendar** showing the shop's day (Aug 31, from `desk.date_today`, not the wall clock), a token meter for the shift, the model chip (`gpt-6-luna`), an **"on desk" name field** (your signature), a connection light, and **↺ Fresh shift** (reset).

---

## How the agents read differently

Every agent has a seat, a colour, an emoji, a one-line personality and **its own voice in type**. You can tell who's talking without reading the name:

| Agent | Seat | Colour | Voice |
|---|---|---|---|
| 👑 **Boss** | Head of the table | Gold | Heavier, bolder text. Gold frame around its call in the shift report |
| 📦 **Inventory** | Left | Sky blue | Plain and factual |
| 💵 **Accounting** | Right | Mint | **Monospace, tabular numbers**: it sounds like a ledger |
| 🏠 **Facilities** | Lower left | Lavender | Soft lavender text |
| 💌 **Customer Service** | Lower right | Pink | **Italic serif**: it reads like a handwritten note, because its job is the kind letter to the customer |

**Live state at the table.** Each seat shows what that agent is doing *right now*, worked out from the event stream:
- **Seat status:** off duty / thinking / checking the books / waiting on *X* / done, plus how many tool calls it has made.
- **Activity ring:** an active agent's avatar grows slightly and gets a pulsing ring in its colour.
- **Speech bubble:** shows the agent's latest words, plus chips for the exact MCP calls it just made, such as `check_stock(CC-TEE-WHITE, S, 1)`.
- **Handoff lines:** when one agent delegates to another, an **animated pink line flows across the table** from asker to helper, and settles to a faint dotted line when the reply comes back. Repeat handoffs get a ×2 badge. Specialist-to-specialist handoffs (Facilities → Accounting) are visible in a way a plain log could never show.
- **"Not needed":** after a run, agents the Boss didn't call are greyed out and labelled. That makes the Problem 6 comparison (*did the Boss call only who was needed?*) visible at a glance.

**The live wire** is the full transcript. It has:
- agent messages with a left border in the agent's colour
- tool calls as pink code chips (hover for the full arguments)
- handoffs as dashed "Boss → Inventory" cards quoting the task, and replies as solid "↩" cards
- tool results folded into an expandable "↳ … answered" line, so the wire stays readable but nothing is hidden

**The shift report** shows what each agent did on the ticket's latest run:
- **The Boss's call** at the top: the final status, its decision, and a ☐ checklist of what the human must do.
- **One card per specialist:** its summary, what it created (green), what blocked it (amber), the MCP tools it used with counts, and who it delegated to.
- **Customer Service's drafts**, shown as letters on cream paper marked "not sent · stays on the board".

The report is built from `output/audit_trail.json` through `GET /api/tickets/{id}/summary`, so it survives a backend restart.

---

## How resolved tickets show up

A ticket moves through visible stages:

1. **open** → button: **▶ Put the team on it**
2. **team on it**: the paper ticket glows pink, the header pill blinks, and the table lights up
3. **needs you · N**: the run finished and the Boss queued requests. The ticket and header turn amber, and the button reads "Waiting on your signature"
4. **back to the Boss**: everything is signed. With the *"hand back to the Boss after I sign"* toggle on (the default), the desk hands the ticket straight back. The Boss reads the log, checks `list_payments`, and closes it
5. **resolved**: a pink **RESOLVED rubber stamp thumps onto the paper ticket** (it scales in and settles at an angle), a big stamp lands on the header, the pill turns green, the button becomes "✓ Resolved", and the spike's progress bar fills

**When a ticket needs your judgement**, not just a signature (in the run, #103 couldn't be fully filled with the cash on hand), the header shows a **✍️ note to the Boss** box. Your note lands on the ticket log as `Human (your name)`, shows up on the live wire in warm amber, and the Boss follows it on the next hand-back. That keeps the human in charge of business calls without letting agents decide them.

The stamp exists because the moment a ticket closes should feel satisfying, like slamming a stamp on a receipt.

Why the hand-back step: in this shop the team usually *can't* finish in one run, because money needs your signature first. Marking a ticket resolved the instant a run ends would lie about rent that hasn't been paid. The ticket is only stamped when the Boss sets `resolved` in the database, and the auto hand-back makes that happen without extra clicks.

---

## How cash shows up

- **The till** shows the checking balance from `GET /api/cash` in big monospace numbers. When an approved payment lands, the number **counts down** (eased over about 1.4 seconds), flashes pink, and a **"−$2,400.00" chip drops off** the side.
- **A balance bar** shows cash in mint, with the money already promised to pending requests as **pink candy stripes**. Below it: "waiting on you $X · left after that $Y" (turns red if it would go negative). Before you sign anything, you can see whether the shop can afford everything on your desk.
- **Receipts:** every paid (or refused) request **prints as a little cream receipt** with a torn zig-zag bottom, the pay tool's exact result line, and your signature in italic pink.
- **Approval slips** in *Needs your signature* show:
  - the amount, large
  - which agent prepared it, in that agent's colour
  - the reason
  - an amber **⚠ warning when the pay tool would refuse**, e.g. a purchase order whose vendor still has an open invoice ("approve #1 first")

  Approve is disabled until you type your name in *on desk*, since agents prepare and only a human approves.
- **Toasts** in the top-right confirm money events in plain words: "Paid $2,400.00 — till now $1,000.00", "Pay tool refused #2: …".

---

## Small things that make it a desk people enjoy

- **Paper vs. screen:** tickets, the calendar, receipts and customer letters are cream paper, while the agents and the system are glowing black glass. The human-world objects are physical; the AI-world objects are light.
- **Motion:** pulsing rings, flowing handoff lines, the "typing…" dots on the wire, the stamp, the till countdown, receipts printing top to bottom. Motion only marks things that are alive or just changed, and all of it turns off under `prefers-reduced-motion`.
- **Plain-language labels:** "Ticket spike", "The till", "Needs your signature", "Fresh shift", "team is on it", "not needed". They read like a shop, not a database.
- **Deep links:** `http://localhost:5173/#103` opens straight to ticket 103.
- **Token meter:** the top bar shows tokens used this shift, so you can see what each run costs. Multi-agent chats burn tokens fast.
- **Honest numbers only:** every value on screen comes from the backend routes (and through them the MCP server). The desk never computes balances or makes up dates itself.

---

## Routes the desk calls (Problem 7)

`GET /api/tickets` · `POST /api/tickets/{id}/run` · `GET /api/events?since=N` (polled about every 1s while the team works, every 2.5s otherwise) · `GET /api/tickets/{id}/summary` · `GET /api/approvals` · `POST /api/approvals/{id}/approve` and `/reject` · `GET /api/cash` · `POST /api/reset` · `GET /api/health`
