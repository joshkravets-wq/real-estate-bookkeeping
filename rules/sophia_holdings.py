"""
Rules module for Sophia Holdings LLC reconciliation.

Architecture:
- Property-owning LLC, 7 properties (4 stabilized rentals, 3 pre-stab vacant lots)
- Single bank account: PCB 6207 (Penn Community 9000856207)
- 3 active loans, all on stabilized properties, all P+I
- 4 members: Steve, Josh, Gene, Boris (same as 10th Fairmount, GJ Holdings)
- RentRedi for tenant rent (suffix 6207)
- No credit cards
- Intercompany: occasional reimbursements with G&J Group (e.g., 2139 N 7th insurance)
"""

ENTITY = {
    "name": "Sophia Holdings LLC",
    "ein": "TBD",
    "address": "TBD",
    "bank_accounts": ["PCB 6207"],
    "credit_cards": [],
    "income_account": "Rental Income",
    "cogs_basis": "cash",
    "rentredi_bank_suffix": "6207",
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
    # Stabilized rentals
    "1934 N 3rd St": {"status": "stabilized", "expense_sheet": "1LhECwr8rLI8TazvHVUzCfd_IYSeugK8fnCBm3Ksxy54"},
    "2139 N 7th St": {"status": "stabilized", "expense_sheet": "1vlCXXcTl_NzpCCy5aNTeEA5ldqIncDKoR25pH1p_mLM"},
    "438 W Susquehanna Ave": {"status": "stabilized", "expense_sheet": "17Vj8a1bAB5ECoAtrhyMGLnp7yn2IRr8LvnYKMXFqIME"},
    "2143 N Palethorp St": {"status": "stabilized", "expense_sheet": "1jhMJ99CUEGt9_kjZLBs8FUZGQMl0aRDZxrU4J-UuHyk"},
    # Pre-stab vacant lots
    "2148 N 3rd St": {"status": "pre-stab", "expense_sheet": "1S7kzFulZoF0qK1XijC_TVnXpWxmGOgZ-WUc7S805mGc"},
    "2411 N 3rd St": {"status": "pre-stab", "expense_sheet": "10Q7HPvvdniYzwbOUq2Zds_wRIgL6-0cpZm55e6_PL2Y"},
    "2024 Wilder St": {"status": "pre-stab", "expense_sheet": "10p6_ZBq_xQqWwuq2TaaiQfT90tqMbCtTNfQd7jhzB0U"},
}

# Active loans (Mar 2026 balances confirmed from loan statements)
LOANS = {
    "9000918635": {
        "property": "2139 N 7th St",
        "rate": None,  # TBD from loan terms
        "monthly_total": 2759.22,
        "servicer": "PCB",
        "loan_csv": "Loan 8635 april-june.csv",
        "format": "pcb",
        "is_stabilized": True,
    },
    "9000918594": {
        "property": "1934 N 3rd St",
        "rate": None,
        "monthly_total": 2336.58,
        "servicer": "PCB",
        "loan_csv": "Loan 8594 april-june.csv",
        "format": "pcb",
        "is_stabilized": True,
    },
    "9001227499": {
        "property": "438 W Susquehanna Ave",
        "rate": None,
        "monthly_total": 2139.58,
        "servicer": "PCB",
        "loan_csv": "Loan 7499 april-june.csv",
        "format": "pcb",
        "is_stabilized": True,
    },
}


# =========================================================
# WATER RANKING CONFIG (consumed by reconcile/water_ranking.py)
# =========================================================
# Fixed-amount rules: amount -> (qb_account, qb_class, type, label)
WATER_FIXED_RULES = {
    21.04: ("2411 N 3rd St", "", "Asset", "2411 N 3rd recurring (pre-stab vacant lot)"),
    35.05: ("Water Expense", "2143 N Palethorp St", "Expense", "2143 Palethorp recurring (subject to change)"),
    106.78: ("Water Expense", "438 W Susquehanna Ave", "Expense", "438 W Susquehanna recurring (subject to change)"),
}

# LIST of lot-style alternating groups (same amount, chronologically alternating across properties)
WATER_LOT_CONFIG = [
    # Group 1: $21.64 alternating between 2 vacant lots (pre-stab -> Asset)
    {"amount": 21.64, "properties": ["2024 Wilder St", "2148 N 3rd St"], "type": "Asset"},
    # Group 2: $33.25 fire service lines, both stabilized properties (Expense, with class)
    {"amount": 33.25, "properties": ["1934 N 3rd St", "2139 N 7th St"], "type": "Expense"},
]

# Variable rank (per month, after fixed + lot): rank-1 = highest, rank-N = Nth
WATER_VARIABLE_RANK = [
    ("Water Expense", "2139 N 7th St", "Expense", "regular water rank-1"),
    ("Water Expense", "1934 N 3rd St", "Expense", "regular water rank-2"),
    ("Water Expense", "438 W Susquehanna Ave", "Expense", "regular water rank-3 (backup if Susquehanna fixed amt changes)"),
    ("Water Expense", "2143 N Palethorp St", "Expense", "regular water rank-4 (backup if Palethorp fixed amt changes)"),
]

# No skip-amount logic for Sophia
WATER_RANK_FALLBACK_SKIP_IF_AMOUNT = None
WATER_RANK_FALLBACK = None

# =========================================================
# PECO RANKING CONFIG (consumed by reconcile/peco_ranking.py)
# =========================================================
# Rank within month (highest amount first) -> (qb_account, qb_class, type, label)
PECO_RANKING_ORDER = [
    ('PECO Expense', '2139 N 7th St', 'Expense', 'rank-1 highest'),
    ('PECO Expense', '1934 N 3rd St', 'Expense', 'rank-2'),
    ('PECO Expense', '438 W Susquehanna Ave', 'Expense', 'rank-3'),
]  # rank-3 already in WATER_VARIABLE_RANK

BANK_RULES = [
    {
        "name": "American Water monthly - 2143 N Palethorp (per Josh, Jul 2026)",
        "match": {"description_contains": "AMERICAN WATER"},
        "account": "Water Expense",
        "class": "2143 N Palethorp St",
        "type": "Expense",
    },
    # RentRedi deposits - flagged for RentRedi loader pass
    {
        'name': 'RentRedi rental deposit',
        'match': {'description_contains': 'RENTREDI'},
        'account': 'RENTREDI_SPLIT',
        'class': 'RENTREDI_SPLIT',
        'type': 'Income',
        'notes': 'Split per unit via RentRedi loader, suffix 6207.',
    },

    # =========================================================
    # WATER BILLS - flagged for water_ranking pass
    # =========================================================
    {
        "name": "Water bill (resolved by water ranking pass)",
        "match": {"description_contains": "CITYOFPHILA"},
        "account": "WATER_RANKING",
        "class": "WATER_RANKING",
        "type": "Mixed",
        "notes": "Water ranking pass assigns property by fixed/lot/rank logic.",
    },

    # =========================================================
    # PECO BILLS - flagged for peco_ranking pass
    # =========================================================
    {
        'name': 'PECO bill (resolved by peco ranking pass)',
        'match': {'description_contains': 'PECO Energy'},
        'account': 'PECO_RANKING',
        'class': 'PECO_RANKING',
        'type': 'Expense',
        'notes': 'Peco ranking pass assigns by rank within month.',
    },

    # =========================================================
    # LOAN PAYMENTS - split via loan CSV parser
    # =========================================================
    {
        "name": "PCB Loan 9000918635 (2139 N 7th) - split via loan CSV",
        "match": {
            "any_description_contains": ["9000918635", "Transfer to 9000918635"],
            "amount_equals": 2759.22,
        },
        "account": "SPLIT_LOAN",
        "class": "9000918635",
        "type": "Liability",
        "notes": "Stabilized: principal → PCB Loan 9000918635, interest → Interest Expense + class 2139 N 7th St",
    },
    {
        "name": "PCB Loan 9000918594 (1934 N 3rd) - split via loan CSV",
        "match": {
            "any_description_contains": ["9000918594", "Transfer to 9000918594"],
            "amount_equals": 2336.58,
        },
        "account": "SPLIT_LOAN",
        "class": "9000918594",
        "type": "Liability",
        "notes": "Stabilized.",
    },
    {
        "name": "PCB Loan 9001227499 (438 W Susquehanna) - split via loan CSV",
        "match": {
            "any_description_contains": ["9001227499", "Loan Payment"],
            "amount_equals": 2139.58,
        },
        "account": "SPLIT_LOAN",
        "class": "9001227499",
        "type": "Liability",
        "notes": "Stabilized. Description is 'Regular Payment Loan Payment' (no transfer-from suffix).",
    },
]

ADMIN_RECLASSIFICATIONS = []

MANUAL_OVERRIDES_FILE_ID = None  # Use universal Manual Overrides Sheet

UNMATCHED_HANDLING = {
    "method": "review",
    "ask_threshold_amount": 0.00,
}

# Bank check patterns observed in property expense sheets when Sophia Holdings is paying
BANK_CHECK_PATTERNS = [
    "sophia holdings",
    "sophia",
    "echeck-bare",
]

# Entity names that disqualify a bare "echeck" match
BANK_CHECK_EXCLUDE_ENTITIES = [
    "vj assets", "vj",
    "jbk", "cambria",
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
