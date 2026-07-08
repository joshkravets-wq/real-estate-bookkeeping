"""
Rules module for SJ Developers LLC reconciliation.

- 2 pre-stab vacant lots: 2151 N 19th St, 2307 N 11th St
- Members: Steve, Josh
- Bank: TD 4412681002. No loans, no RentRedi, no rent.
- Q1 2026 bank activity: 6 stormwater bills only.
- Intercompany: JBK Homes fronted 2307 N 11th costs (tax $881.88 +
  architect $3,000 - Nochumson refund $114.68) = Due to JBK Homes LLC
  $3,767.20 — booked via off-bank journal MO rows.
"""

ENTITY = {
    "name": "SJ Developers LLC",
    "ein": "TBD",
    "address": "TBD",
    "bank_accounts": ["TD 4412681002"],
    "credit_cards": [],
    "income_account": "Other Income",
    "cogs_basis": "cash",
    "rentredi_bank_suffix": None,
    "members": ["Steve Kravets", "Josh Kravets"],
    "equity_accounts": {
        "Steve Kravets": {
            "contribution": "Steve Kravets Capital:Contribution",
            "draws": "Steve Kravets Capital:Draws",
        },
        "Josh Kravets": {
            "contribution": "Josh Kravets Capital:Contribution",
            "draws": "Josh Kravets Capital:Draw",
        },
    },
}

PROPERTIES = {
    "2151 N 19th St": {"status": "pre-stab", "expense_sheet": None},
    "2307 N 11th St": {"status": "pre-stab", "expense_sheet": None},
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

BANK_CHECK_PATTERNS = ["sj developers", "sj", "echeck-bare"]
BANK_CHECK_EXCLUDE_ENTITIES = [
    "vj assets", "vj", "jbk", "sophia", "cambria", "veit",
    "gj holdings", "phily properties", "g&j group", "gj group",
    "10th fairmount", "skira", "galloway", "sergeant",
]

RETAIL_VENDOR_PATTERNS = [
    "cityofphila", "city of phila", "phila dept rev",
    "td bank", "penn community",
]

WATER_FIXED_RULES = {}
WATER_LOT_CONFIG = [
    {"amount": 21.64, "properties": ["2151 N 19th St", "2307 N 11th St"], "type": "Asset", "wrap": True},
]
WATER_VARIABLE_RANK = []
WATER_RANK_FALLBACK_SKIP_IF_AMOUNT = None
WATER_RANK_FALLBACK = None
