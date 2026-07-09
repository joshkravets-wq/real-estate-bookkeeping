"""
Rules module for Phily Properties LLC reconciliation.

Architecture:
- Property-owning LLC, 3 properties (2 stabilized rentals + 1 pre-stab lot)
- TWO bank accounts: PCB 9757 (Penn 9000769757) + TD 0855 (TD 0373210855)
- 1 loan: PCB 9000743074 on 2210 Amber St ($1,953.89/mo P+I)
- 2 members: Steve, Victoria (equity cluster size = 2)
- RentRedi deposits to TD (suffix 0855)
- Intercompany: 10th Fairmount pays 1010 Fairmount stormwater -> they book
  "Due from Phily Properties"; watch for reimbursements here (Due to 10th Fairmount)
"""

ENTITY = {
    "name": "Phily Properties LLC",
    "ein": "TBD",
    "address": "TBD",
    "bank_accounts": ["PCB 9757", "TD 0373210855"],
    "credit_cards": [],
    "income_account": "Rental Income",
    "cogs_basis": "cash",
    "rentredi_bank_suffix": "0855",
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
    "1212 N 27th St": {"status": "stabilized", "expense_sheet": None},
    "2210 Amber St": {"status": "stabilized", "expense_sheet": None},
    "1010 Fairmount Ave": {"status": "pre-stab", "expense_sheet": None},
}

LOANS = {
    "9000743074": {
        "property": "2210 Amber St",
        "rate": None,
        "monthly_total": 1953.89,
        "servicer": "PCB",
        "loan_csv": "Jan-March Loan 2210 amber.csv",
        "format": "pcb",
        "is_stabilized": True,
    },
}

BANK_RULES = [
    {
        "name": "Steven Kravets private mortgage payment (recurring $550 check)",
        "match": {"description_contains": "CHECK", "amount_equals": 550.00},
        "account": "Loan from Steven Kravets",
        "class": "",
        "type": "Liability",
    },
    {
        "name": "Samuel Foschini rent (2210 Amber unit, outside RentRedi)",
        "match": {"description_contains": "SAMUEL FOSCHINI"},
        "account": "Rental Income",
        "class": "2210 Amber St",
        "type": "Income",
    },
    {
        "name": "PECO (all Penn PECO = 2210 Amber)",
        "match": {"description_contains": "PECO"},
        "account": "PECO Expense",
        "class": "2210 Amber St",
        "type": "Expense",
    },
    {
        "name": "Comcast (all TD Comcast = 1212 N 27th)",
        "match": {"description_contains": "COMCAST"},
        "account": "Internet Expense",
        "class": "1212 N 27th St",
        "type": "Expense",
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
        "notes": "Split per unit via RentRedi loader, TD suffix 0855.",
    },
    {
        "name": "Water bill (resolved by water ranking pass)",
        "match": {"description_contains": "CITYOFPHILA"},
        "account": "WATER_RANKING",
        "class": "WATER_RANKING",
        "type": "Mixed",
    },
    {
        "name": "PCB Loan 9000743074 (2210 Amber) - split via loan CSV",
        "match": {
            "any_description_contains": ["9000743074", "Ln pymnt *3074", "3074"],
        },
        "account": "SPLIT_LOAN",
        "class": "9000743074",
        "type": "Liability",
        "notes": "Stabilized: principal -> PCB Loan 9000743074, interest -> Interest Expense + class 2210 Amber St",
    },
]

ADMIN_RECLASSIFICATIONS = []
MANUAL_OVERRIDES_FILE_ID = None
UNMATCHED_HANDLING = {"method": "review", "ask_threshold_amount": 0.00}

BANK_CHECK_PATTERNS = ["phily properties", "phily", "echeck-bare"]
BANK_CHECK_EXCLUDE_ENTITIES = [
    "vj assets", "vj", "jbk", "sophia", "cambria",
    "gj holdings", "veit", "g&j group", "gj group",
    "10th fairmount", "skira", "galloway", "sergeant",
]

RETAIL_VENDOR_PATTERNS = [
    "peco", "philadelphia gas", "phila gas", "pgw",
    "cityofphila", "city of phila", "city of philadelphia",
    "phila dept rev", "comcast",
    "foremost", "homesite", "us assure",
    "td bank", "penn community", "rentredi",
]

# Water config: learn from first run
WATER_FIXED_RULES = {
    138.85: ("Water Expense", "2210 Amber St", "Expense", "2210 Amber recurring (PCB)"),
    33.25: ("Water Expense", "2210 Amber St", "Expense", "2210 Amber fire service line (PCB)"),
    21.64: ("1010 Fairmount Ave", "", "Asset", "1010 Fairmount lot stormwater (TD)"),
}
WATER_LOT_CONFIG = []
# Variable bills (TD side) -> 1212 N 27th; two slots for months with 2 bills
WATER_VARIABLE_RANK = [
    ("Water Expense", "1212 N 27th St", "Expense", "rank-1"),
    ("Water Expense", "1212 N 27th St", "Expense", "rank-2 (also 1212)"),
]
WATER_RANK_FALLBACK_SKIP_IF_AMOUNT = None
WATER_RANK_FALLBACK = None

# Unmatched RentRedi deposits default to 2210 Amber (per Josh, Jul 2026)
RENTREDI_NO_MATCH_DEFAULT = ("Rental Income", "2210 Amber St")
