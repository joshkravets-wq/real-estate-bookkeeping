"""
Rules module for Sergeant Street LLC reconciliation.

- 1 pre-stab vacant lot: 822 N 12th St
- Members: Steve, Victoria
- Bank: PCB 4777 (Penn 9001394777). No loans, no RentRedi, no rent.
- Everything capitalizes to the single lot.
"""

ENTITY = {
    "name": "Sergeant Street LLC",
    "ein": "TBD",
    "address": "TBD",
    "bank_accounts": ["PCB 4777"],
    "credit_cards": [],
    "income_account": "Other Income",
    "cogs_basis": "cash",
    "rentredi_bank_suffix": None,
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
    "822 N 12th St": {"status": "pre-stab", "expense_sheet": None},
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
        "name": "Phila Dept Rev (single-lot entity: capitalize to 822 N 12th)",
        "match": {"description_contains": "PHILA DEPT"},
        "account": "822 N 12th St",
        "class": "",
        "type": "Asset",
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

BANK_CHECK_PATTERNS = ["sergeant", "echeck-bare"]
BANK_CHECK_EXCLUDE_ENTITIES = [
    "vj assets", "vj", "jbk", "sophia", "cambria", "veit",
    "gj holdings", "phily properties", "g&j group", "gj group",
    "10th fairmount", "skira", "galloway", "sj developers",
]

RETAIL_VENDOR_PATTERNS = [
    "cityofphila", "city of phila", "phila dept rev",
    "td bank", "penn community",
]

WATER_FIXED_RULES = {
    21.64: ("822 N 12th St", "", "Asset", "822 N 12th lot stormwater"),
}
WATER_LOT_CONFIG = []
WATER_VARIABLE_RANK = []
WATER_RANK_FALLBACK_SKIP_IF_AMOUNT = None
WATER_RANK_FALLBACK = None
