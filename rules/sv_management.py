"""
Rules module for SV Management LLC reconciliation.

- Steven's management company: NO properties, service income only.
- Members: Steve, Victoria. Bank: TD 4335733039.
- Income = management fees from family entities (Galloway, Phily, 10th
  Fairmount incl. $30K post-sale fee via check #155, Veit, others).
- Two credit cards booked as separate expense accounts (per Josh):
  Capital One + Chase. No card itemization.
- No loans, no RentRedi, no water-ranking (water bills -> Water Expense, no class).
"""

ENTITY = {
    "name": "SV Management LLC",
    "ein": "TBD",
    "address": "TBD",
    "bank_accounts": ["TD 4335733039"],
    "credit_cards": [],
    "income_account": "Management Fee Income",
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

PROPERTIES = {}

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
        "name": "Management fee deposits (all deposits are fees per Josh)",
        "match": {"description_contains": "DEPOSIT"},
        "account": "Management Fee Income",
        "class": "",
        "type": "Income",
    },
    {
        "name": "Capital One card (separate account per Josh)",
        "match": {"description_contains": "CAPITAL ONE"},
        "account": "Capital One Card Expense",
        "class": "",
        "type": "Expense",
    },
    {
        "name": "Chase card (separate account per Josh)",
        "match": {"description_contains": "CHASE CARD"},
        "account": "Chase Card Expense",
        "class": "",
        "type": "Expense",
    },
    {
        "name": "Keystone Health insurance",
        "match": {"description_contains": "KEYSTONE HEALTH"},
        "account": "Health Insurance Expense",
        "class": "",
        "type": "Expense",
    },
    {
        "name": "T-Mobile",
        "match": {"description_contains": "T-MOBILE"},
        "account": "Telephone Expense",
        "class": "",
        "type": "Expense",
    },
    {
        "name": "Water (no properties: Water Expense, no class)",
        "match": {"description_contains": "CITYOFPHILA"},
        "account": "Water Expense",
        "class": "",
        "type": "Expense",
    },
    {
        "name": "PECO (office)",
        "match": {"description_contains": "PECO"},
        "account": "Office Expense",
        "class": "",
        "type": "Expense",
    },
    {
        "name": "Verizon (office)",
        "match": {"description_contains": "VERIZON"},
        "account": "Office Expense",
        "class": "",
        "type": "Expense",
    },
]

ADMIN_RECLASSIFICATIONS = []
MANUAL_OVERRIDES_FILE_ID = None
UNMATCHED_HANDLING = {"method": "review", "ask_threshold_amount": 0.00}

BANK_CHECK_PATTERNS = ["sv management", "sv man", "echeck-bare"]
BANK_CHECK_EXCLUDE_ENTITIES = [
    "vj assets", "vj", "jbk", "sophia", "cambria", "veit",
    "gj holdings", "phily properties", "g&j group", "gj group",
    "10th fairmount", "skira", "galloway", "sergeant", "sj developers",
]

RETAIL_VENDOR_PATTERNS = [
    "cityofphila", "city of phila", "phila dept rev", "us treasury",
    "keystone health", "t-mobile", "peco", "verizon", "usma",
    "capital one", "chase card", "td bank", "penn community",
]

WATER_FIXED_RULES = {}
WATER_LOT_CONFIG = []
WATER_VARIABLE_RANK = []
WATER_RANK_FALLBACK_SKIP_IF_AMOUNT = None
WATER_RANK_FALLBACK = None
