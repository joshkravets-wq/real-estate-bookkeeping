"""
Rules module for VJ Assets LLC reconciliation.

Architecture:
- Property-owning LLC, 5 properties (1 stabilized rental + 4 pre-stab)
- Single bank account: PCB 3771 (Penn Community 9000963771)
- 1 loan: PCB 9000998562 on 1950 N Orianna St (P+I, no escrow)
- 4 members: Victoria, Josh, Gene, Boris (NOTE: Victoria, NOT Steve)
- RentRedi suffix 3771
- No credit cards
- 2672 Braddock Ave: G&J Group did construction here in Q1 (canonical suffix: Ave)
"""

ENTITY = {
    "name": "VJ Assets LLC",
    "ein": "TBD",
    "address": "TBD",
    "bank_accounts": ["PCB 3771"],
    "credit_cards": [],
    "income_account": "Rental Income",
    "cogs_basis": "cash",
    "rentredi_bank_suffix": "3771",
    "members": ["Victoria Kravets", "Josh Kravets", "Gene Kravets", "Boris Boloborodov"],
    "equity_accounts": {
        "Victoria Kravets": {
            "contribution": "Victoria Kravets - Capital",
            "draws": "Victoria Kravets - Capital",
        },
        "Josh Kravets": {
            "contribution": "Josh Kravets Capital:Contribution",
            "draws": "Josh Kravets Capital:Draw",
        },
        "Gene Kravets": {
            "contribution": "Gene Kravets Capital:Contribution",
            "draws": "Gene Kravets Capital:Draws",
        },
        "Boris Boloborodov": {
            "contribution": "Boris Capital:Contribution",
            "draws": "Boris Capital:Draw",
        },
    },
}

PROPERTIES = {
    # Stabilized rental
    "1950 N Orianna St": {"status": "stabilized", "expense_sheet": None},
    # Pre-stab
    "6826 Hegerman St": {"status": "pre-stab", "expense_sheet": "1wpUNQxSIjxrHw4SW59yKaKE69hTWPujGU2_l1lt3NGY"},
    "2672 Braddock Ave": {"status": "pre-stab", "expense_sheet": "1C7HjOzD76WAkSYb47DI7AfBxtHyAEeak9wNS3TSIGOw"},
    "634 W Cumberland St": {"status": "pre-stab", "expense_sheet": "1wiHllhPg7tZw6mPM5d-g2fFEf9Gos2jBCGVQ6TPPwZs"},
    "1005 Hall St": {"status": "pre-stab", "expense_sheet": "1marxFjOJlyS_zoF8Dl8jKxHdnfjjlfufY7HrCFttzSw"},
}

LOANS = {
    "9000998562": {
        "property": "1950 N Orianna St",
        "rate": None,
        "monthly_total": 1073.01,
        "servicer": "PCB",
        "loan_csv": "loan 8562 april-june.csv",
        "format": "pcb",
        "is_stabilized": True,
    },
}

BANK_RULES = [
    # Stuck NSF fees -> Bank Service Charges
    {
        "name": "NSF fee (stuck)",
        "match": {"description_contains": "Insufficient Funds Charge"},
        "account": "Bank Service Charges",
        "class": "",
        "type": "Expense",
    },
    # RentRedi deposits - flagged for RentRedi loader pass
    {
        "name": "RentRedi rental deposit",
        "match": {"description_contains": "RENTREDI"},
        "account": "RENTREDI_SPLIT",
        "class": "RENTREDI_SPLIT",
        "type": "Income",
        "notes": "Split per unit via RentRedi loader, suffix 3771.",
    },
    # Water bills - flagged for water_ranking pass
    {
        "name": "Water bill (resolved by water ranking pass)",
        "match": {"description_contains": "CITYOFPHILA"},
        "account": "WATER_RANKING",
        "class": "WATER_RANKING",
        "type": "Mixed",
    },
    # Loan payment - split via loan CSV parser
    {
        "name": "PCB Loan 9000998562 (1950 N Orianna) - split via loan CSV",
        "match": {
            "any_description_contains": ["9000998562", "Regular Payment"],
            "amount_equals": 1073.01,
        },
        "account": "SPLIT_LOAN",
        "class": "9000998562",
        "type": "Liability",
        "notes": "Stabilized: principal -> PCB Loan 9000998562, interest -> Interest Expense + class 1950 N Orianna St",
    },
]

ADMIN_RECLASSIFICATIONS = []

MANUAL_OVERRIDES_FILE_ID = None  # Use universal Manual Overrides Sheet

UNMATCHED_HANDLING = {
    "method": "review",
    "ask_threshold_amount": 0.00,
}

BANK_CHECK_PATTERNS = [
    "vj assets",
    "vj",
    "echeck-bare",
]

BANK_CHECK_EXCLUDE_ENTITIES = [
    "jbk", "sophia", "cambria",
    "gj holdings", "veit", "phily properties",
    "g&j group", "gj group",
    "10th fairmount", "skira",
]

RETAIL_VENDOR_PATTERNS = [
    "peco", "philadelphia gas", "phila gas", "pgw",
    "cityofphila", "city of phila", "city of philadelphia",
    "phila dept rev", "phila26 li", "phila l&i",
    "foremost", "homesite", "homeowners insurance", "us assure",
    "td bank", "penn community",
    "rentredi",
]

# Water config: learn from first run. Explicitly empty = unmatched water goes to review.
WATER_FIXED_RULES = {
    21.04: ("2672 Braddock Ave", "", "Asset", "2672 Braddock recurring stormwater (pre-stab)"),
    81.49: ("Water Expense", "1950 N Orianna St", "Expense", "1950 N Orianna recurring"),
}
WATER_LOT_CONFIG = [
    {"amount": 21.64, "properties": ["634 W Cumberland St", "1005 Hall St"], "type": "Asset", "wrap": True},
]
# Both variable ranks go to 1950 N Orianna (months can have 2 variable bills, e.g. Mar $94.13 + $68.84)
WATER_VARIABLE_RANK = [
    ("Water Expense", "1950 N Orianna St", "Expense", "rank-1"),
    ("Water Expense", "1950 N Orianna St", "Expense", "rank-2 (also Orianna)"),
]
WATER_RANK_FALLBACK_SKIP_IF_AMOUNT = None
WATER_RANK_FALLBACK = None
