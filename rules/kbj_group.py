"""
Rules module for KBJ Group LLC reconciliation.

- Josh's payroll entity (single member: Josh). NO properties.
- Bank: TD 4434313732 (only account; no cards, no loans, no RentRedi).
- Q1 2026 activity is one story: 2025 payroll check to Josh ($25,000,
  written 12/30/25 as check #1003) bounced 1/30/26, was reversed 2/2/26,
  and was re-issued as check #1004, clearing 2/9/26. Josh topped up the
  account with $2,000 from his personal checking (x3504) on 2/2/26 to
  cover the overdraft.
- Cash-basis note for accountant: the $25k is 2025 payroll re-issued and
  actually paid 2/9/2026 (original check bounced). Confirm 2025 books /
  payroll filings treatment to avoid double-counting wages.
"""

ENTITY = {
    "name": "KBJ Group LLC",
    "ein": "TBD",
    "address": "TBD",
    "bank_accounts": ["TD 4434313732"],
    "credit_cards": [],
    "income_account": "Other Income",
    "cogs_basis": "cash",
    "rentredi_bank_suffix": None,
    "members": ["Josh Kravets"],
    "equity_accounts": {
        "Josh Kravets": {
            "contribution": "Josh Kravets Capital:Contribution",
            "draws": "Josh Kravets Capital:Draw",
        },
    },
}

PROPERTIES = {}

LOANS = {}

BANK_RULES = [
    {
        "name": "Check #1003 - 2025 payroll to Josh (bounced 1/30, reversed 2/2 - debit and credit net to zero)",
        "match": {"description_contains": "CHECK # 1003"},
        "account": "Payroll Expenses",
        "class": "",
        "type": "Expense",
    },
    {
        "name": "Check #1004 - 2025 payroll to Josh, re-issued after #1003 bounced; written 12/30/25, cleared 2/9/26",
        "match": {"description_contains": "CHECK # 1004"},
        "account": "Payroll Expenses",
        "class": "",
        "type": "Expense",
    },
    {
        "name": "Transfer from Josh personal checking x3504 (covering bounced-check overdraft)",
        "match": {"description_contains": "Transfer from CK x3504"},
        "account": "Josh Kravets Capital:Contribution",
        "class": "",
        "type": "Equity",
    },
    {
        "name": "NSF fee (stuck)",
        "match": {"description_contains": "Insufficient Funds Charge"},
        "account": "Bank Service Charges",
        "class": "",
        "type": "Expense",
    },
]

ADMIN_RECLASSIFICATIONS = []
MANUAL_OVERRIDES_FILE_ID = None
UNMATCHED_HANDLING = {"method": "review", "ask_threshold_amount": 0.00}

BANK_CHECK_PATTERNS = ["kbj", "echeck-bare"]
BANK_CHECK_EXCLUDE_ENTITIES = [
    "vj", "sophia", "jbk", "cambria", "10th fairmount", "veit",
    "phily properties", "gj holdings", "g&j", "sergeant", "galloway",
    "dauphin", "sj developers", "sv management",
]
