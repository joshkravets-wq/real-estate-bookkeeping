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
        "loan_csv": "loan 8251 jan-march.csv",
        "format": "pcb",
        "is_stabilized": True,
    },
    "9000829048": {
        "property": "1948 N Orianna St",
        "rate": 6.200,
        "monthly_total": 1125.60,
        "servicer": "PCB",
        "loan_csv": "loan 9048 jan-march.csv",
        "format": "pcb",
        "is_stabilized": True,
    },
    "0000426433": {
        "property": "507 W Dauphin St",
        "rate": 5.900,
        "monthly_total": 1674.72,
        "servicer": "Fay",
        "loan_csv": "507 W Dauphin Loan History jan-march.csv",
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

BANK_RULES = [
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
        "match": {"description_contains": "PECO"},
        "account": "PECO_SPLIT",
        "class": "PECO_SPLIT",
        "type": "Asset",
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

RETAIL_VENDOR_PATTERNS = []
