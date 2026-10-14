"""The Campus Customs agent team. Importing this package builds all five agents.

  boss.py              Boss              reads tickets, routes work, makes the final call
  inventory.py         Inventory         stock by SKU/size, shortfalls, restock vendor
  accounting.py        Accounting        cash, invoices, margins, payment/PO requests for human approval
  facilities.py        Facilities        leases and rent
  customer_service.py  Customer Service  customer message drafts (never sent)
"""

# Import order = roster order on the dashboard. Each import registers its agent.
from agents import boss  # noqa: F401, I001
from agents import inventory  # noqa: F401
from agents import accounting  # noqa: F401
from agents import facilities  # noqa: F401
from agents import customer_service  # noqa: F401
from agents.base import AGENTS, SPECS

AGENT_NAMES = list(SPECS)
