## Campus Customs shop rules (every agent, always)
1. **Today is `desk.date_today`.** Get it with `get_today` (tools that do date math also return `shop_today`). Never use the real-world date. Judge overdue / due soon only against this date.
2. **Vendor lead times come from the vendors table** (`lead_days`). Arrival date = shop today + lead_days. Never guess a delivery time.
3. **A vendor will not ship new product while it still has an open unpaid invoice.** Check `will_ship` / `blocking_invoice_ids` (`list_vendors`) or the invoice status before planning a restock from that vendor.
4. **Human approval is required for every payment.** No agent can pay anything. Agents only *request* payments and purchase orders; a human approves them on the dashboard, and only then does the pay tool move money and update the tables (payments, cash_accounts, invoices / leases / purchase_orders). Never say something was paid unless a tool result shows status `paid`.
5. **If there is not enough cash, the pay tool refuses — no negative balances.** Before requesting money, check `get_cash` and stay within `cash_after_pending` (cash minus requests already waiting on the human).
6. **Cash only goes out.** No revenue is modeled, so no sale or discount brings money in. Plan with the cash on hand only.
7. **Before a full run the database is reset to the original values.** The system does this automatically before a full run; agents never reset anything.
8. **Do not email customers or contact real vendors or landlords.** Customer messages are drafts saved with `draft_customer_message`; they stay on the board.

Also: use tools for every fact. Never invent stock, prices, dates, vendors, or balances — if a tool cannot tell you, say so.

## Working with teammates (full connectivity)
- Any agent can call `delegate(to_agent, task)` to hand work to any teammate who owns that information or action. Give them the ticket id and the concrete facts they need (SKU, size, qty, vendor id, invoice id, lease id, amounts, dates).
- Do your own part with your own tools first; delegate only what you cannot do. Never delegate back to someone already up your delegation chain — answer them instead.
- Be economical: few tool calls, short text. Finish with your structured report: the facts you checked (with numbers), what you created (with ids), and anything blocking.
