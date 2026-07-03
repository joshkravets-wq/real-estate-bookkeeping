"""
Rules module for Cambria Group LLC reconciliation.

Architecture:
- Property-owning LLC, 8 properties (1 stabilized rental + 6 pre-stab vacant lots + 1 mortgage-only)
- Single bank account: PCB 0100 (Penn Community 9001180100)
- NO loans
- 4 members: Steve, Josh, Gene, Boris (same as Sophia Holdings, GJ Holdings)
- RentRedi for tenant rent (suffix 0100)
- No credit cards
- Intercompany: Due from Cambria on GJ Holdings books (Cambria paid 6541 Edmund RE tax in error);
  2563 E Elkhart renovation payments to G&J Group are capitalized (major renovation)
- 1512-16 Broad St mortgage is Steve & Joe only; not expected to touch this account
"""

ENTITY = {
    "name": "Cambria Group LLC",
    "ein": "TBD",
    "address": "TBD",
    "bank_accounts": ["PCB 0100"],
    "credit_cards": [],
    "income_account": "Rental Income",
    "cogs_basis": "cash",
    "rentredi_bank_suffix": "0100",
    "members": ["Steve Kravets", "Josh Kravets", "Gene Kravets", "Boris Boloborodov"],
    "equity_accounts": {
        "Steve Kravets": {
            "contribution": "Steve Kravets Capital:Contribution",
            "draws": "Steve Kravets Capital:Draws",
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

# Property registry
PROPERTIES = {
    # Stabilized rental
    "2563 E Elkhart St": {"status": "pre-stab", "expense_sheet": "1V_1L2cAwlahesTmMe_JVudb31ssixzQ_5rE-rpAsjSA"},
    # Sold 5/2026; owned during Q1. Not in master inventory (inventory post-dates sale).
    "3435 Mercer St": {"status": "pre-stab", "expense_sheet": None},
    # Pre-stab vacant lots
    "2110 E Cambria St": {"status": "pre-stab", "expense_sheet": "1zhbBLXMb1s--7MuuZAx8cAVSZfFW6aIMBiVZSFCB1Bk"},
    "2119 N Hope St": {"status": "pre-stab", "expense_sheet": "1poC6x7-QDnKucUSnpoo1pzGNXAL5YNaMMown18a_npc"},
    "1430 N Marston St": {"status": "pre-stab", "expense_sheet": "1xnFPzEnZtU6XhCWqNwN-xC3k_V02_8HrpLsWABa3pN4"},
    "2505 Jefferson St": {"status": "pre-stab", "expense_sheet": "1U95hZKsg6mbxsfufnD8oMWQUExQBZ9-48f6cfvUAGms"},
    "542 Edgley St": {"status": "pre-stab", "expense_sheet": "1_Vu2Jl-ENx9sAqHK-J-qmjNOWKdzM_JJ1050BpQlgzU"},
    "946 N 43rd St": {"status": "pre-stab", "expense_sheet": "1JJ6Mu7xgZtB-rfJvNApZp1Dm3YUNlH36REEuETpPkEU"},
}

# No loans
LOANS = {}

BANK_RULES = [
    # Stuck NSF fees (no reversal within 3 days) -> Bank Service Charges
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
        "notes": "Split per unit via RentRedi loader, suffix 0100.",
    },
    # Water bills - flagged for water_ranking pass
    {
        "name": "Water bill (resolved by water ranking pass)",
        "match": {"description_contains": "CITYOFPHILA"},
        "account": "WATER_RANKING",
        "class": "WATER_RANKING",
        "type": "Mixed",
        "notes": "Water ranking pass assigns property by fixed/lot/rank logic.",
    },
]

ADMIN_RECLASSIFICATIONS = []

MANUAL_OVERRIDES_FILE_ID = None  # Use universal Manual Overrides Sheet

UNMATCHED_HANDLING = {
    "method": "review",
    "ask_threshold_amount": 0.00,
}

BANK_CHECK_PATTERNS = [
    "cambria group",
    "cambria",
    "echeck-bare",
]

BANK_CHECK_EXCLUDE_ENTITIES = [
    "vj assets", "vj",
    "jbk", "sophia",
    "gj holdings", "veit", "phily properties",
    "g&j group", "gj group",
    "10th fairmount",
]

RETAIL_VENDOR_PATTERNS = [
    "peco", "philadelphia gas", "phila gas", "pgw",
    "cityofphila", "city of phila", "city of philadelphia",
    "phila dept rev", "phila26 li", "phila l&i",
    "foremost", "homesite", "homeowners insurance",
    "td bank", "penn community",
    "rentredi",
]

# Water config: TBD after first engine run shows the actual bill amounts.
# Vacant lots likely have $21.64-style recurring; 2563 E Elkhart variable.
WATER_FIXED_RULES = {
    21.04: ("2110 E Cambria St", "", "Asset", "2110 E Cambria recurring stormwater (pre-stab)"),
}
WATER_LOT_CONFIG = [
    # wrap=True: months with more bills than properties keep alternating (3rd bill -> property[0], etc.)
    {"amount": 21.64, "properties": ["1430 N Marston St", "2119 N Hope St"], "type": "Asset", "wrap": True},
]
WATER_VARIABLE_RANK = []  # no variable rank; unmatched water bills go to review
WATER_RANK_FALLBACK_SKIP_IF_AMOUNT = None
WATER_RANK_FALLBACK = None
