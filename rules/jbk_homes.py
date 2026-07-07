"""
Rules module for JBK Homes LLC reconciliation.

- 2 pre-stab vacant lots: 5128 Warren St (deed not recorded), 2445 N Orkney St
- Single member: Josh (no equity clusters)
- Bank: TD 4366464108; Capital One card ("JBK Card") paid from bank
- Card payments booked directly to Marketing Expense (per Josh, Jul 2026)
- Also fronts costs for SJ Developers' 2307 N 11th St -> Due from SJ Developers LLC
- No loans, no RentRedi, no rent
"""

ENTITY = {
    "name": "JBK Homes LLC",
    "ein": "TBD",
    "address": "TBD",
    "bank_accounts": ["TD 4366464108"],
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

PROPERTIES = {
    "5128 Warren St": {"status": "pre-stab", "expense_sheet": None},
    "2445 N Orkney St": {"status": "pre-stab", "expense_sheet": None},
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
        "name": "Capital One card payment -> Marketing Expense (per Josh)",
        "match": {"description_contains": "CAPITAL ONE CRCARDPMT"},
        "account": "Marketing Expense",
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
    {
        "name": "PECO (office)",
        "match": {"description_contains": "PECO"},
        "account": "Office Expense",
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

BANK_CHECK_PATTERNS = ["jbk", "echeck-bare"]
BANK_CHECK_EXCLUDE_ENTITIES = [
    "vj assets", "vj", "sophia", "cambria", "veit",
    "gj holdings", "phily properties", "g&j group", "gj group",
    "10th fairmount", "skira", "galloway", "sergeant",
]

RETAIL_VENDOR_PATTERNS = [
    "peco", "cityofphila", "city of phila", "phila dept rev",
    "verizon", "capital one", "philadelphia par",
    "td bank", "penn community",
]

WATER_FIXED_RULES = {
    21.64: ("2445 N Orkney St", "", "Asset", "2445 N Orkney lot stormwater"),
}
WATER_LOT_CONFIG = []
WATER_VARIABLE_RANK = []
WATER_RANK_FALLBACK_SKIP_IF_AMOUNT = None
WATER_RANK_FALLBACK = None
