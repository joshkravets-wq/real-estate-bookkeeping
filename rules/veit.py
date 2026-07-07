"""
Rules module for Veit LLC reconciliation.

- 7 properties: 5 stabilized rentals + 2 pre-stab lots (1006 + 1008 Fairmount)
- Single bank: TD 0373971472 (full-number account name, like Phily's TD)
- No loans. RentRedi suffix 1472.
- 2 members: Steve, Victoria (equity cluster size 2)
- Intercompany: 10th Fairmount pays 1008 Fairmount stormwater -> books
  "Due from Veit LLC" ($64.92 in Q1). Watch for reimbursement out of this account.
- Tenant water reimbursements: Veit pays 4773 Loring water; tenant Paul Dunbar
  reimburses exact amounts via RentRedi ("Utilities water" category).
"""

ENTITY = {
    "name": "Veit LLC",
    "ein": "TBD",
    "address": "TBD",
    "bank_accounts": ["TD 0373971472"],
    "credit_cards": [],
    "income_account": "Rental Income",
    "cogs_basis": "cash",
    "rentredi_bank_suffix": "1472",
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
    "5427 Horrocks St": {"status": "stabilized", "expense_sheet": None},
    "4773 Loring St": {"status": "stabilized", "expense_sheet": None},
    "903 Pratt St": {"status": "stabilized", "expense_sheet": None},
    "9712-26 Bustleton Ave": {"status": "stabilized", "expense_sheet": None},
    "10201 Bustleton Ave": {"status": "stabilized", "expense_sheet": None},
    "1006 Fairmount Ave": {"status": "pre-stab", "expense_sheet": None},
    "1008 Fairmount Ave": {"status": "pre-stab", "expense_sheet": None},
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
        "notes": "Split per unit via RentRedi loader, TD suffix 1472.",
    },
    {
        "name": "Water bill (resolved by water ranking pass)",
        "match": {"description_contains": "CITYOFPHILA"},
        "account": "WATER_RANKING",
        "class": "WATER_RANKING",
        "type": "Mixed",
    },
    {
        "name": "Section 8 rent (9712-26 Bustleton Ave)",
        "match": {"description_contains": "PHILADELPHIA HOU S8"},
        "account": "Rental Income",
        "class": "9712-26 Bustleton Ave",
        "type": "Income",
    },
]

ADMIN_RECLASSIFICATIONS = []
MANUAL_OVERRIDES_FILE_ID = None
UNMATCHED_HANDLING = {"method": "review", "ask_threshold_amount": 0.00}

BANK_CHECK_PATTERNS = ["veit", "echeck-bare"]
BANK_CHECK_EXCLUDE_ENTITIES = [
    "vj assets", "vj", "jbk", "sophia", "cambria",
    "gj holdings", "phily properties", "g&j group", "gj group",
    "10th fairmount", "skira", "galloway", "sergeant",
]

RETAIL_VENDOR_PATTERNS = [
    "peco", "philadelphia gas", "phila gas", "pgw",
    "cityofphila", "city of phila", "city of philadelphia",
    "phila dept rev", "phila26 l&i", "comcast",
    "contributionship", "philadelphia hou",
    "td bank", "penn community", "rentredi",
]

# Water: fixed rules for known recurring; rest TBD from Josh's mapping
WATER_FIXED_RULES = {
    110.91: ("Water Expense", "4773 Loring St", "Expense", "Loring water (tenant reimburses via RentRedi)"),
    123.55: ("Water Expense", "4773 Loring St", "Expense", "Loring water (tenant reimburses via RentRedi)"),
    21.64: ("1006 Fairmount Ave", "", "Asset", "1006 Fairmount lot stormwater (1008 paid by 10th Fairmount)"),
}
WATER_LOT_CONFIG = []
WATER_VARIABLE_RANK = []  # TBD
WATER_RANK_FALLBACK_SKIP_IF_AMOUNT = None
WATER_RANK_FALLBACK = None

RENTREDI_NO_MATCH_DEFAULT = None  # TBD if needed
