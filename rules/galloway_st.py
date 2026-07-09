"""
Rules module for Galloway St LLC reconciliation.

- 1 stabilized rental: 1114 N Galloway St. Members: Steve, Victoria.
- Bank: PCB 4917 (Penn 9001394917). RentRedi suffix 4917.
- Holds a $170K mortgage receivable on FinnLand's 5 properties (no Q1
  payments observed; watch future quarters).
- Private loan from Steven Kravets on the property: $720 check payments
  -> "Loan from Steven Kravets" liability.
- Single property: all taxes/water route to 1114 N Galloway.
"""

ENTITY = {
    "name": "Galloway St LLC",
    "ein": "TBD",
    "address": "TBD",
    "bank_accounts": ["PCB 4917"],
    "credit_cards": [],
    "income_account": "Rental Income",
    "cogs_basis": "cash",
    "rentredi_bank_suffix": "4917",
    "members": ["Steve Kravets", "Victoria Kravets"],
    "equity_accounts": {
        "Steve Kravets": {
            "contribution": "Steve Kravets Capital:Contribution",
            "draws": "Steve Kravets Capital:Draws",
        },
        "Victoria Kravets": {
            "contribution": "Victoria Kravets - Capital",
            "draws": "Victoria Kravets - Capital",
        },
    },
}

PROPERTIES = {
    "1114 N Galloway St": {"status": "stabilized", "expense_sheet": None},
}

LOANS = {}

BANK_RULES = [
    {
        "name": "Steven Kravets private loan payment (recurring $720 check)",
        "match": {"description_contains": "Check", "amount_equals": 720.00},
        "account": "Loan from Steven Kravets",
        "class": "",
        "type": "Liability",
    },
    {
        "name": "NSF fee (stuck)",
        "match": {"description_contains": "Insufficient Funds Charge"},
        "account": "Bank Service Charges",
        "class": "",
        "type": "Expense",
    },
    {
        "name": "RentRedi rental deposit",
        "match": {"description_contains": "RENTREDI"},
        "account": "RENTREDI_SPLIT",
        "class": "RENTREDI_SPLIT",
        "type": "Income",
        "notes": "Split per unit via RentRedi loader, suffix 4917.",
    },
    {
        "name": "Phila Dept Rev (single rental: Taxes - Phila / 1114 N Galloway)",
        "match": {"description_contains": "PHILA DEPT"},
        "account": "Taxes - Phila",
        "class": "1114 N Galloway St",
        "type": "Expense",
    },
    {
        "name": "Water bill (resolved by water ranking pass)",
        "match": {"description_contains": "CITYOFPHILA"},
        "account": "WATER_RANKING",
        "class": "WATER_RANKING",
        "type": "Mixed",
    },
]

ADMIN_RECLASSIFICATIONS = []
MANUAL_OVERRIDES_FILE_ID = None
UNMATCHED_HANDLING = {"method": "review", "ask_threshold_amount": 0.00}

BANK_CHECK_PATTERNS = ["galloway", "echeck-bare"]
BANK_CHECK_EXCLUDE_ENTITIES = [
    "vj assets", "vj", "jbk", "sophia", "cambria", "veit",
    "gj holdings", "phily properties", "g&j group", "gj group",
    "10th fairmount", "skira", "sergeant", "sj developers",
]

RETAIL_VENDOR_PATTERNS = [
    "cityofphila", "city of phila", "phila dept rev",
    "td bank", "penn community", "rentredi",
]

WATER_FIXED_RULES = {
    33.25: ("Water Expense", "1114 N Galloway St", "Expense", "1114 N Galloway fire service line"),
}
WATER_LOT_CONFIG = []
WATER_VARIABLE_RANK = [
    ("Water Expense", "1114 N Galloway St", "Expense", "rank-1 (only property)"),
    ("Water Expense", "1114 N Galloway St", "Expense", "rank-2 (only property)"),
]
WATER_RANK_FALLBACK_SKIP_IF_AMOUNT = None
WATER_RANK_FALLBACK = None
