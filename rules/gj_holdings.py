"""
Rules module for GJ Holdings LLC reconciliation.

Architecture:
- Property-owning LLC, 11 active properties
- Pre-stab: ALL costs CAPITALIZED to property asset (QB Account = property address, no class)
- Stabilized: expenses to expense accounts WITH property class
- 3 active loans (PCB 9000798251, PCB 9000829048, Fay 0000426433)
- Capital contributions and distributions (4 members: Steve, Josh, Gene, Boris)
- Rental income from RentRedi (3 stabilized properties + occasional units)
- No credit cards (uses G&J Group as contractor)
"""

ENTITY = {
    "name": "GJ Holdings LLC",
    "ein": "TBD",
    "address": "TBD",
    "bank_accounts": ["PCB 3395"],
    "credit_cards": [],
    "income_account": "Rental Income",
    "cogs_basis": "cash",
    "rentredi_bank_suffix": "3395",
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

# Property registry: pre-stab vs stabilized determines accounting treatment
PROPERTIES = {
    # Stabilized rentals
    "314 W Norris St": {"status": "stabilized", "expense_sheet": "1qW72_3toUAXdN1d3slcXPjdETXVq5nIk_TKuXMjT4S0"},
    "1948 N Orianna St": {"status": "stabilized", "expense_sheet": "1R4PMsDDQq-ChS-B_yp20_5sJO6lYOg3zKM8S5ixHYkI"},
    "507 W Dauphin St": {"status": "stabilized", "expense_sheet": "1j-o-S52019bDhUOUG5NVY5WnsXGkbquUIZ3iWyEWbus"},
    # Pre-stab houses
    "5461 W Berks St": {"status": "pre-stab", "expense_sheet": "1tp1IX4hqlmPXKhYGDkuKa91rCNx5xklyoMW6TZpTSbs"},
    "5746 Grays Ave": {"status": "pre-stab", "expense_sheet": "1kKNKkzX9zJTKjCkx4DYHoJ1ZSZs97pWQNps3xTmG99U"},
    "2433 N 6th St": {"status": "pre-stab", "expense_sheet": "1aSa3NnrLyIYvR8Tv-uboboFFfUPWUhomOWMsYU1LdHY"},
    "2428 N Fairhill St": {"status": "pre-stab", "expense_sheet": "1xUn7F3HOTuf2L8QlCrq-8f6tdN5KicO96fvJvzr77KE"},
    "7338 N 20th St": {"status": "pre-stab", "expense_sheet": "1r_NZDbk4phpUN-WONZPBniraJQrq34JmAfCvx6zYfNY"},
    "6541 Edmund St": {"status": "pre-stab", "expense_sheet": "13MHbVjDIvgH9nzImVZWO4hK20f-I1n8drYg5fTNu3pc"},
    # Pre-stab vacant lots
    "2415 N 4th St": {"status": "pre-stab", "expense_sheet": "10VZtxIy7-vc4uOJ7u8XhK79uvRXOCZQF1nqW3N8VviA"},
    "2431 N 3rd St": {"status": "pre-stab", "expense_sheet": "1D1TjG6XdDxGdAHs3B_oY7WYOlIDWKBFgFyU9Z2bFx4k"},
}

# Active loans
LOANS = {
    "9000798251": {
        "property": "314 W Norris St",
        "rate": 4.350,
        "monthly_total": 2011.09,
        "servicer": "PCB",
        "loan_csv": "loan 8251 april-june.csv",
        "format": "pcb",
        "is_stabilized": True,
    },
    "9000829048": {
        "property": "1948 N Orianna St",
        "rate": 6.200,
        "monthly_total": 1125.60,
        "servicer": "PCB",
        "loan_csv": "loan 9048 april-june.csv",
        "format": "pcb",
        "is_stabilized": True,
    },
    "0000426433": {
        "property": "507 W Dauphin St",
        "rate": 5.900,
        "monthly_total": 1674.72,
        "servicer": "Fay",
        "loan_csv": "507 W Dauphin Loan History april-june.csv",
        "format": "fay",
        "is_stabilized": True,
    },
}

# Water ranking config (used by water ranking pass)
WATER_RANKING_ORDER_HOUSES = [
    "314 W Norris St",      # 1st = largest
    "507 W Dauphin St",     # 2nd
    "1948 N Orianna St",    # 3rd
    "5461 W Berks St",      # 4th
    "5746 Grays Ave",       # 5th
]
WATER_RANKING_ORDER_LOTS = [
    "2415 N 4th St",
    "2431 N 3rd St",
]
WATER_LOT_THRESHOLD = 25.00  # bills below this are considered lot bills

# Gas/PECO 50/50 splits
GAS_PECO_SPLIT = [
    "5461 W Berks St",
    "5746 Grays Ave",
]


# =========================================================
# WATER RANKING CONFIG (consumed by reconcile/water_ranking.py)
# =========================================================
# Fixed-amount rules: amount -> (qb_account, qb_class, type, label)
# For pre-stab properties: qb_account = property address, no class.
# For stabilized properties: qb_account = "Water Expense", class = property address.
WATER_FIXED_RULES = {
    33.25: ("Water Expense", "314 W Norris St", "Expense", "sprinkler line"),
    35.05: ("5461 W Berks St", "", "Asset", "5461 W Berks recurring (pre-stab)"),
    49.23: ("Water Expense", "314 W Norris St", "Expense", "other unit"),
    81.49: ("Water Expense", "1948 N Orianna St", "Expense", "Orianna recurring"),
}

# Lots: same amount, alternate chronologically among properties
WATER_LOT_CONFIG = {
    "amount": 21.64,
    "properties": ["2415 N 4th St", "2431 N 3rd St"],
    "wrap": True,  # months can have >2 lot bills (e.g. next cycle billed on the 30th)
}

# Variable-rank: rank-1 (highest) -> entry[0], rank-2 (2nd) -> entry[1]
# Rank-3 (3rd) uses WATER_RANK_FALLBACK below (if WATER_RANK_FALLBACK_SKIP_IF_AMOUNT not seen).
WATER_VARIABLE_RANK = [
    ("Water Expense", "314 W Norris St", "Expense", "regular water"),
    ("Water Expense", "507 W Dauphin St", "Expense", "regular water"),
]
WATER_RANK_FALLBACK_SKIP_IF_AMOUNT = 81.49  # if $81.49 (Orianna recurring) present this month, skip rank-3
WATER_RANK_FALLBACK = ("Water Expense", "1948 N Orianna St", "Expense", "Orianna fallback")


BANK_RULES = [
    {
        "name": "HomeServe USA repair plan - 507 W Dauphin St (per Josh, Jul 2026)",
        "match": {"description_contains": "HOMESERVE"},
        "account": "Repairs & Maintenance",
        "class": "507 W Dauphin St",
        "type": "Expense",
    },
    # =========================================================
    # LOAN PAYMENTS - flagged for split via loan CSV parser
    # =========================================================
    {
        "name": "PCB Loan 9000798251 (314 W Norris) - split via loan CSV",
        "match": {
            "description_contains": "9000798251",
            "amount_equals": 2011.09,
        },
        "account": "SPLIT_LOAN",
        "class": "9000798251",
        "type": "Liability",
        "notes": "Split into principal + interest via loan_payments loader.",
    },
    {
        "name": "PCB Loan 9000829048 (1948 N Orianna) - split via loan CSV",
        "match": {
            "description_contains": "9000829048",
            "amount_equals": 1125.60,
        },
        "account": "SPLIT_LOAN",
        "class": "9000829048",
        "type": "Liability",
    },
    {
        "name": "Fay Loan 0000426433 (507 W Dauphin) - split via Fay CSV",
        "match": {
            "any_description_contains": ["FAY SERVICING", "FAY", "0000426433"],
            "amount_equals": 1674.72,
        },
        "account": "SPLIT_LOAN",
        "class": "0000426433",
        "type": "Liability",
        "notes": "Split into principal + interest + escrow via loan_payments loader.",
    },

    # =========================================================
    # WATER BILLS - flagged for water ranking pass
    # =========================================================
    {
        "name": "Water bill (resolved by water ranking pass)",
        "match": {"description_contains": "CITYOFPHILA"},
        "account": "WATER_RANKING",
        "class": "WATER_RANKING",
        "type": "Mixed",
        "notes": "Water ranking pass assigns property by ranking amounts within each month.",
    },

    # =========================================================
    # GAS BILLS - 50/50 split pass
    # =========================================================
    {
        "name": "Phila Gas (50/50 Berks/Grays split)",
        "match": {"description_contains": "PHILADELPHIA GAS"},
        "account": "GAS_SPLIT",
        "class": "GAS_SPLIT",
        "type": "Asset",
    },

    # =========================================================
    # PECO ELECTRIC - 50/50 split pass
    # =========================================================
    {
        "name": "PECO (50/50 Berks/Grays split)",
        "match": {"any_description_contains": ["PECO", "PHILADELPHIA ELE"]},
        "account": "PECO_SPLIT",
        "class": "PECO_SPLIT",
        "type": "Asset",
    },

    # Intercompany transfers to G&J Group 5494 (contractor payments)
    {
        "name": "Contractor payment to G&J Group",
        "match": {
            "any_description_contains": [
                "Gj holding to gj. 5494",
                "GJ hold to 5494",
                "Gj holdings to GJ 5494",
                "Contractor payment GJ hold to 5494",
                "Contractor payment from GJ Holding",
                "Contractor payment from GJ Holdings",
                "Contractor payment",
                "credit card bill",
            ],
        },
        "account": "ASK",
        "class": "ASK",
        "type": "Asset",
        "notes": "Contractor payment to G&J Group. Class via Manual Override for now; future: descriptions will include property tag.",
    },

    # Tiny SuperValue purchases (under $20)
    {
        "name": "SuperValue Check fee",
        "match": {"description_contains": "SuperValue Check"},
        "account": "Bank Service Charges",
        "class": "",
        "type": "Expense",
    },

    # =========================================================
    # RENTREDI deposits - flagged for RentRedi loader pass
    # =========================================================
    {
        "name": "RentRedi rental deposit",
        "match": {"description_contains": "RENTREDI"},
        "account": "RENTREDI_SPLIT",
        "class": "RENTREDI_SPLIT",
        "type": "Income",
        "notes": "Split per unit via RentRedi loader, matched on bank suffix 3395 + amount + date.",
    },
]

ADMIN_RECLASSIFICATIONS = []

MANUAL_OVERRIDES_FILE_ID = None  # Create when needed

UNMATCHED_HANDLING = {
    "method": "review",
    "ask_threshold_amount": 0.00,
}

# Bank check patterns observed in property expense sheets when GJ Holdings PCB 3395
# is the paying account. Catches "gj holdings", "gj holdings 1023", "gj holdings bank", etc.
BANK_CHECK_PATTERNS = [
    "gj holdings",          # explicit GJ Holdings markings
    "echeck-bare",          # bare "echeck" entries that don't mention other entities
]

# Entity names that, if mentioned in payment_method, disqualify a bare "echeck" match
BANK_CHECK_EXCLUDE_ENTITIES = [
    "vj assets",
    "vj",
    "sophia",
    "jbk",
    "cambria",
    "10th fairmount",
    "veit",
    "phily properties",
    "g&j group",
    "gj group",
]

RETAIL_VENDOR_PATTERNS = [
    "peco", "philadelphia gas", "phila gas", "pgw",
    "cityofphila", "city of phila", "city of philadelphia",
    "phila dept rev",
    "register of wills", "department of state",
    "phila revenue", "internal revenue",
    "chase", "amex", "penn community",
    "home depot", "lowe", "amazon",
    "diamond state insurance",
    "american modern insurance",
    "liberty mutual", "geico",
]
