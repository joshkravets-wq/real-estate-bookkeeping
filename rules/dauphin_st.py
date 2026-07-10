"""
Rules module for Dauphin St LLC reconciliation.

- 1 stabilized rental: 2101 E Dauphin St (2 units, RentRedi suffix 4826)
- Members: Steve, Victoria. Bank: PCB 4826 (Penn 9001394826).
- Private loan from Steve: $760 checks -> "Loan from Steven Kravets"
- Q1 note: 1/13 tax $3,900.92 = prior-year/delinquent RE tax (still
  Taxes - Phila); 2/4 -$1,500 to Sasha Ortiz = security deposit return
  to departed unit-1 tenant -> Security Deposits Held liability.
"""

ENTITY = {
    "name": "Dauphin St LLC",
    "ein": "TBD",
    "address": "TBD",
    "bank_accounts": ["PCB 4826"],
    "credit_cards": [],
    "income_account": "Rental Income",
    "cogs_basis": "cash",
    "rentredi_bank_suffix": "4826",
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
    "2101 E Dauphin St": {"status": "stabilized", "expense_sheet": None},
}

LOANS = {}

BANK_RULES = [
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
        "notes": "Split per unit via RentRedi loader, suffix 4826.",
    },
    {
        "name": "Steven Kravets private loan payment (recurring $760 check)",
        "match": {"description_contains": "Check", "amount_equals": 760.00},
        "account": "Loan from Steven Kravets",
        "class": "",
        "type": "Liability",
    },
    {
        "name": "Phila Dept Rev (single rental: Taxes - Phila / 2101 E Dauphin)",
        "match": {"description_contains": "PHILA DEPT"},
        "account": "Taxes - Phila",
        "class": "2101 E Dauphin St",
        "type": "Expense",
    },
    {
        "name": "PECO (single rental)",
        "match": {"description_contains": "PECO"},
        "account": "PECO Expense",
        "class": "2101 E Dauphin St",
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

BANK_CHECK_PATTERNS = ["dauphin st llc", "dauphin", "echeck-bare"]
BANK_CHECK_EXCLUDE_ENTITIES = [
    "vj assets", "vj", "jbk", "sophia", "cambria", "veit",
    "gj holdings", "phily properties", "g&j group", "gj group",
    "10th fairmount", "skira", "galloway", "sergeant", "sj developers",
    "sv management",
]

RETAIL_VENDOR_PATTERNS = [
    "cityofphila", "city of phila", "phila dept rev", "peco",
    "rentredi", "td bank", "penn community", "moneyline",
]

WATER_FIXED_RULES = {
    33.25: ("Water Expense", "2101 E Dauphin St", "Expense", "2101 E Dauphin fire service line"),
}
WATER_LOT_CONFIG = []
WATER_VARIABLE_RANK = [
    ("Water Expense", "2101 E Dauphin St", "Expense", "rank-1 (only property)"),
    ("Water Expense", "2101 E Dauphin St", "Expense", "rank-2 (only property)"),
]
WATER_RANK_FALLBACK_SKIP_IF_AMOUNT = None
WATER_RANK_FALLBACK = None

# Unmatched RentRedi deposits default to the only property
RENTREDI_NO_MATCH_DEFAULT = ("Rental Income", "2101 E Dauphin St")
