# HW5 — AI Prompts Log

A log of what I typed to my vibe coder (Claude Code) for each HW5 problem.

---

## Setup — Workspace check (before Problem 0)

**Prompt I typed:**

> We will be working on hw5 folder today. Please put everything today there. Write a joke in the folder to make sure you can find it

**Follow-up prompt:** None needed.

---

## Problem 0 — Scenario and data

**Prompt I typed:**

> Campus Customs Multi-Agent Operations is the agentic team that runs the shop. Open tickets land on a board - customer orders, rent, unpaid bills, discount requests, whatever the shop has to handle. I want to build three pieces that talk to each other: an MCP server, a FastAPI backend with a multi-agent team, and a Reach dashboard so a human can watch the agents at work and approve requests.
>
> The agent team has full connectivity - any agent may delegate tasks to any other agent for help. In this assignment, I want to build these agents:
>
> * Boss - reads each ticket, decides who should work on it, and makes final calls
> * Inventory - checks stock by SKU and size, spots shortfalls,  and figures out which vendor can restock
> * Accounting - watches cash and invoices, checks margins, and prepares payments or purchase orders for human approval
> * Facilities - handles the shop space side (leases, rent, etc.)
> * Customer Service - drafts messages for customers.
>
> Data - I have added data.zip into the hw5 folder. Unzip if it still zipped. The data I have is data/campus_customs. db. That file is the original shop database. Please confirm that tables include desk, tickets, inventory, pricing, vendors, leases, cash_accounts, payments, and invoices.
>
> My tools will update the database as tickets get resolved. Make a copy of the database file and call it data/campus_customs_new.db and point your MCP server and backend at that working copy. Keep campus_customs.db untouched so you can restn when you want to restart resolving the tickets.
>
> Here are the rules of this shop:
>
> * The field desk.date_today is 'today' for the shop. Use this date to determine what is overdue
> * Vendor lead times comes from the vendors table
> * A vendor will not ship new product while they still have an open unpaid invoice
> * Human approval is required for any payments. Points will be deducted if this is not done. If payment is made, make sure to update the relevant table
> * If there is not enough cash, the pay tool must refuse - no negative balances
> * Cash only goes out in this homework - we did not model revenue, so no money comes in.
> * Before a full run to resolve the tickets, make sure to reset the database to the original values
> * Do not email customers or call real vendors. Drafts stay on the board
>
> Use my PORTKEY_API_KEY for AI calls. For this assigment, use only gpt-7-luna through Portkey for every agent. Multi-agent chats burn tokens fast. Points will be deducted if any other model shows up in my code or runs.

**Follow-up prompts:**

> It is important that we only use gpt-6-luna through portkey for every agent. Could your reconfirm that you will use it

> Sorry, that was an error. We are only using 6 for all the tasks in this assignment. Please update accordingly

**What was lacking after the first prompt:** My first prompt named the wrong model (gpt-7-luna), so the agents were built on a model that Portkey quietly forwarded to gpt-5.6-luna, and I had to correct it to gpt-6-luna.

---

## Problem 1 — Vibe coder prompts

**Prompt I typed:**

> We are now starting with problem 1 titled vibe coder prompts. Here create AI_prompts.md at the start of the assignment and keep it updated as I work. The fole is the log of what I typed to my vibe coder. Put one section for each problem. Each section must include:
>
> * The problem number and title
> * At least on prompt I typed
> * One follow-up prompt if I needed it (and one sentence on what was lacking after the first one)

**Follow-up prompt:** None needed yet.

---

## Problem 2 — Study the Campus Customs database

**Prompt I typed:**

> We are now moving to problem 2 titled Study the Campus Customs database. Here open data/campus_customs.db and look through every table and its fields. Copy the original file to data/campus_customs_new.db - later problems update the working copy. Study the three open tickets so you see how likely they link to other tables. Start the output/harness.md. For each table, list the fields and one short line on why that table matters for the agents. I'll keep growing this harness file in later problems

**Follow-up prompt:** None needed yet.

---

## Problem 3 — Build the MCP server

**Prompt I typed:**

> We are now moving to problem 3 titled build the MCP server. Here write an MCP server in mcp_server/using FastMCP. It will talk to data/campus_customs_new.db. You do not need to connect or run it in this problem. Every agent in this homework uses the tools in this MCP server. You will add more tools to it later; for now write three tools you know you will need for the tickets in the database. Keep the names clear. Never invent any data, only use information in the database.
>
> In output/harness.md, list each of your three MCP tools. For every tool include: which table it reads, which ticket it helps unlock (101, 102, or 103), and one sentence on why the tool is the right one for that ticket. Vague lines like 'reads inventory' score low - tie the tool to the ticket.
>
> Also add a short mcp_server/README.md file that explains what the MCP server is for, which database file it uses, and the three tools it has.

**Follow-up prompt:** None needed yet.

---

## Problem 4 — Add the MCP server to vibe coder and test each tool

**Prompt I typed:**

> We are now moving to problem 4 titled add the MCP server to vibe coder and test each tool. Here, add my MCP server to this project so the vibe coder can call the tools. Save the connection JSON text in .mcp.json at the project root (or however you save local MCP server lists). Test each of the three MCP tools. Save the evidence in output/mcp_smoke.json. For every tool include:
>
> * the prompt I asked my vibe coder
> * the tool name
> * the tool output (must match values in data/campus_customs_new.db)

**Follow-up prompts (one per tool, typed in a new session in hw5/ so `campus-customs` loaded):**

> Using the campus-customs MCP, check stock for CC-TEE-WHITE size S for ticket 101 that needs 1 unit.

> Using the campus-customs MCP, get the status of invoice 501 for ticket 101.

> Using the campus-customs MCP, get the rent due for lease 1 for ticket 102.

> Continue HW5 Problem 4 — see the hw5-problem4-smoke memory note.

**What was lacking after the first prompt:** Claude Code only loads a new MCP server when a session starts, so the tools couldn't be called in the session that added them. I had to start a new session in hw5/ and ask for each tool by name so the evidence came from real vibe-coder tool calls.

---

## Problem 5 — Build the agent team and grow MCP tools

**Prompt I typed:**

> We are now moving to problem 5 titled build the agent team and grow MCP tools. Here build the agentic team for Campus Customs using PydanticAI: Boss, Inventory, Accounting, Facilities, and Customer Service. Include prompts, models, and agent loops so they can delegate work to each other with full connectivity. Put the agent prompts in backend/prompts/ - one file per agent. Put the data types in backend/models.py, and the agent files under backend/ (your layout can vary as long as the five rles are clear). Use my PORTKEY_API_KEY and only gpt-6-luna for every agent
>
> I want the agents to follow the shop rules I had outlined earlier and please assign the assignments laid out earlier to each agent in the team. Please confirm that you can still locate all these

**Follow-up prompt:**

> Continuing with problem 5, add any tools the agent need to my MCP server so they can work on the open tickets. Shop facts come from the MCP server over data/campus_customs_new.db - do not invent a second shop-tools layer that bypasses MCP. Wite the agents so they append to output/audit_trail.json as they run: for each agent-loop step, record enough to audit later. Append to this file - do not wipe it each run.
>
> In output/harness.md, list each agent and each MCP tool (including ones you add in this problem) along with which table uses. Also add a short safety section: the guardrails a real business would want when agents touch real customers and real money, plus limits that keep token use in check. Update mcp_server/README.md so the tools list matches what I have now.

**What was lacking after the first prompt:** The first prompt built the team but didn't ask for an audit trail of each agent-loop step, a per-agent/per-tool table map and safety section in the harness, or a README that matched the grown tool list.

---

## Problem 6 — Plan the three tickets

**Prompt I typed:**

> We are now moving to problem 6 titled plan the three tickets. Here before you wire the backend, write down what you expect the team to do on each open tickets. Build output/desk_tickets.html - a page you can double-click with one tab per ticket (101, 102, and 103). Also add empty Cash and Reflection tabs for later problems (leave them blank or with a short 'coming later' note for now). On each ticket tab, fill an Expected section only (leave rooms for an Actual section you will fill after you run the agents). For each ticket's Expected section, write in your own words:
>
> * who the boss should call first, and why
> * All the agent delegations you expect - not 'Boss calls everyone'
> * Which MCP tools you expect that run to use
>
> Plans that send every specialist on evert ticket score low. You will compare this plan to what actually happens when your agent resolve the three tickets

**Follow-up prompt:** None needed yet.

---

## Problem 7 — Backend routes

**Prompt I typed:**

> We are now moving to problem 7 titled Backend routes. My React frontend dashboard (the next problem) needs a backend it can call. In backend/main.py, use FastAPI and add routes that do the following:
>
> * return the three tickets and whether each is open or resolved
> * take a ticked id and run my agent team on that ticket
> * return recent agent events - what each agent said and which tools they used - so the board can refresh
> * approve a payment or purchase after a human clicks approve (agents only prepare the pay; this route is what actually changes cash)
> * return the current checking balance from cash_accounts
> * reset the database to the original values when you want to try a fresh run
>
> From the backend/ folder, start the server with: uvicorn main:app --reload --port 8000
> This turns on my backend at http://localhost:8000 so the frontend dashboard can call those routes. In output/harness.md, list each route in one line (what URL/what it does)

**Follow-up prompt:** None needed yet.

---

## Problem 8 — Agent dashboard

**Prompt I typed:**

> We are now moving to problem 8 titled agent dashboard. Here build the frontend dashboard in frontend/ with React + Vite + TypeScript. The page should call the routes you built in problem 7. At a minimum the board should:
>
> * List all three tickets
> * Let me pick one ticket and start the agent team on it
> * Show each agent and what they are saying/doing while the ticket runs
> * Mark a ticket resolved when the run finishes
> * Show a short summary of what each agent did on the ticket
> * Let a human approve a pay or purchase when asked
> * Show the checking balance (it should drop after an approved pay)
>
> Make the dashboard look good. Be creative with the layout and feel - this is a real desk people would want to sit at, so put thought into how it looks
> Tell the front end to talk to my backend at http://localhost:8000. On the backend, allow the Vite page origin (usually http://localhost:5173) so the browser is allowed to call those routes. Start the board with: npm run dev
> This opens the React desk in my browser so I can pick tickets and watch agents.
> Write output/design.md with what you chose for the dashboard look (layout, how agents read differently, how resolved tickets and cash show up) and why - including the creative choices that make it feel special and something humans would actually enjoy using.

**Follow-up prompt:** None needed yet.

---

## Problem 9 — Resolve the tickets

**Prompt I typed:**

> We are now moving to problem 9 titled resolve the tickets. Here before testing the agents on a full run over the three tickets, reset the working database data/campus_customs_new.db again so that you start clean. Note the starting checking balance. Then run all three tickets on the board (101, 102, 103) until each is resolved. Open output/desk_tickets.html from problem 6. on each ticket tab, fill the actual section from this run: which agents worked, what they delegated, and which tools they used. Keep the expected section so you can compare the two.
> On the cash tab of the same output/desk_tickets.html, itemize the money:
> * Starting checking balance (after the reset)
> * For each ticket: how cash changed when that tickets resolved, and why (which pay/purchase, dollar amount
> * Ending checking balance - it must match cash_accounts in the working database
>
> Wrong cash math loses points even if the board shows every ticket resolved. Also save:
>
> * output/resolved_tickets.json - for each ticket: id, final status, short outcome, what each agent contributed, and any human approvals
> * output/resolved_board.html - a page you can double-click with a screenshot of your Reach board for each resolved ticket (101, 102, and 103)
>
> Append real runs to output/audit_trail.json. Finish output/harness,md so it covers tables, MCP tools, the five agents, API routes, the dashboard and safety rules

**Follow-up (my decision when #103 came back `blocked`):** The vibe coder asked how to close #103, since 20 hoodies were requested, 8 were in stock, and the 12-unit restock cost $264 with only $152 cash. I chose **"Fill the 8 in stock"**: sell the 8 size-M hoodies at the approved $36.67, decline the other 12, and spend nothing more.

**What was lacking after the first prompt:** The prompt assumed every ticket could reach "resolved" through approvals alone. #103 needed a human business decision (how much of the order to fill), and the desk had no way to tell the Boss that, so a human-only "note to the Boss" tool and route were added.

---

## Problem 10 — Reflection

**Prompt I typed:**

> We are now moving to Problem 10 titled reflection. Here open output/desk_tickets.html and fill the reflection tab. Answer in your own vibe, and be detailed thorough:
>
> * How would you evaluate the performance of the agent on each ticket and why?
> * For each ticket, how did actual compare to the expected plan you wrote earlier?
> * What would have been simpler as one agent with tools - and why?
> * Describe three new problems campus customs might face that this agent team could solve with the tools you built
> * Describe three new problems Campus Customs might face that this agent team could solve with tools you built
> * Describe three new problems  Campus Customs might face that this agent team could not solve with the tools you built, and explain the tools and agents you would need to solve them
>
> Tie every answer to this app and the three tickets you ran - use the tickets tabs and cash tab on the same page as your evidence. Generic AI essays without Campus Customs details will score low.

**Follow-up prompt:** None needed yet. (The "could solve" bullet appears twice in my prompt; the reflection answers it once, alongside the "could not solve" section.)

---

## Problem 11 — Submit to GitHub

**Prompt I typed:**

> We are now moving to problem 11 titled submit to github. Here push my code to a public GitHub repository so graders can clone it. Put the repo URL in output/github_url.txt. Do not push my real .env to gitHub repo. Do include both database files under data/ (the original and my working copy) so graders can run my app easily. Please confirm that you have the following as my file layout:
> hw5/ AI_prompts.md, requirements.txt, .env.example, .gitignore, .mcp.json, README.md, data/ (campus_customs.db, campus_customs_new.md), frontend/, backend/ (main/py, models.py, prompts/ boss.md, inventory.md, accounting.md, facilities.md, customer_service.md), output/ (harness.md, mcp_smoke.json, desk_tickets.html, design.md, resolved_tickets.json, resolved_board.html, audit_trail.json, github_url.txt)
>
> README should explain: copy original DB to the working copy when you need a clean run, start MCP server, start FastAPI backend, start React board, reset the DB before a full three-ticket run

**Follow-up prompt:**

> great. before i push this to github, could you confirm that all questions were sufficiently responded to. Are there any outstanding concerns? or things i need to know?

(Then: "yes" to applying the four fixes it found.)

**What was lacking after the first prompt:** The first prompt didn't ask for a final check, which turned up a few gaps before the push: a missing "what was lacking" line for Problem 4, smoke-test values that no longer matched the post-run working database, unpinned dependency versions, and the need to explain why Portkey reports the model as `gpt-6-luna-global`.

