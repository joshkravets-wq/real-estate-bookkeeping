"""
Rules module for 10th Fairmount LLC reconciliation.

Architecture:
- Property-owning LLC, 7 properties (1 sold Feb 2026)
- Two bank accounts: TD 3139011 + PCB 3869
- Pre-stab: ALL costs CAPITALIZED to property asset
- Stabilized: 1252 N 18th St only (route to expense accounts + class)
- 2 active loans (PCB 9000854235 stabilized, PCB 9001254757 pre-stab interest-only)
- 4 members: Steve, Josh, Gene, Boris
- TD account: stormwater splits (1012, 1008R, 1008 Veit) + occasional capital
- PCB 3869: operating account — rent, draws, contractor payments
- Intercompany: 1008 Fairmount = Due from Veit LLC, 1010 Fairmount = Due from Phily Properties LLC
"""

ENTITY = {
    "name": "10th Fairmount LLC",
    "ein": "TBD",
    "address": "1363 Buttonwood Dr, Southampton PA 18966",
    "bank_accounts": ["TD 3139011", "PCB 3869"],
    "credit_cards": [],
    "income_account": "Rental Income",
    "cogs_basis": "cash",
    "rentredi_bank_suffix": "3869",
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
    # Stabilized rental (own books)
    "1252 N 18th St": {
        "status": "stabilized",
        "expense_sheet": "1mcp-DCArKeIi4i5V1lxs-mSg7_YdDBm4I54-kikfgWE",
    },
    # Pre-stab properties (own books)
    "1012 FAIRMOUNT AVENUE": {
        "status": "pre-stab",
        "expense_sheet": "1-m8GX2ebZXizpF_rQAI5wa92NjE-I0eOXa3eEfE8qBU",
        "expense_sheet_notes": "Shared 1006-12 Fairmount sheet covers 1006, 1008, 1008R, 1010, 1012",
    },
    "1008R Fairmount": {
        "status": "pre-stab",
        "expense_sheet": "1-m8GX2ebZXizpF_rQAI5wa92NjE-I0eOXa3eEfE8qBU",
        "expense_sheet_notes": "Shared 1006-12 Fairmount sheet",
    },
    "2925 Master Street": {
        "status": "pre-stab",
        "expense_sheet": "1ojuSpDw1TzHuA9uxnkZN3uUpE_QJMXDAdZtCj_ojrYA",
    },
    # Sold Feb 14 2026 — referenced for post-sale costs (Gain on Sale)
    "2030 N Lawrence St": {
        "status": "sold",
        "sold_date": "2026-02-14",
        "expense_sheet": "1m_LrYHJFxp8eDXJXZPsbK3FKKA1WwlfJCSE-BveSEfU",
    },
    # Intercompany — costs paid by 10th Fairmount, owed by another LLC
    "1008 Fairmount Ave": {
        "status": "intercompany",
        "owed_to": "Due from Veit LLC",
        "expense_sheet": "1-m8GX2ebZXizpF_rQAI5wa92NjE-I0eOXa3eEfE8qBU",
    },
    "1010 Fairmount Ave": {
        "status": "intercompany",
        "owed_to": "Due from Phily Properties LLC",
        "expense_sheet": "1-m8GX2ebZXizpF_rQAI5wa92NjE-I0eOXa3eEfE8qBU",
    },
}

# Active loans
LOANS = {
    "9000854235": {
        "property": "1252 N 18th St",
        "rate": 4.580,
        "monthly_total": 2030.82,
        "servicer": "PCB",
        "loan_csv": "loan 1252 N 18th april-june SYNTH.csv",
        "format": "pcb",
        "is_stabilized": True,
    },
    "9001254757": {
        "property": "2925 Master Street",
        "rate": 7.750,
        "monthly_total": None,  # Interest-only, varies monthly
        "servicer": "PCB",
        "loan_csv": "constructin loan 2925 master.csv",
        "format": "pcb",
        "is_stabilized": False,  # pre-stab → capitalize interest
        "interest_only": True,
    },
}

# Stormwater fixed-amount routing (TD Bank, $21.64 each)
# These are recurring fixed-amount bills. Order doesn't matter — engine uses
# bill ID number if available, otherwise pattern of 3 same-day bills.
STORMWATER_ROUTING_TD = [
    {"amount": 21.64, "account": "1012 FAIRMOUNT AVENUE", "type": "Asset", "class": None},
    {"amount": 21.64, "account": "1008R Fairmount", "type": "Asset", "class": None},
    {"amount": 21.64, "account": "Due from Veit LLC", "type": "Interco", "class": None,
     "notes": "1008 Fairmount Ave — intercompany reimbursable from Veit LLC"},
]

# PCB water amount rules (different from GJ Holdings — 10th Fairmount has single-property routing)
WATER_RULES_PCB = [
    {"amount": 21.64, "account": "Water", "class": "1252 N 18th St", "type": "Expense",
     "notes": "1252 N 18th recurring water"},
    {"amount": 59.33, "account": "Water", "class": "1252 N 18th St", "type": "Expense",
     "notes": "1252 N 18th periodic water"},
    {"amount": 84.62, "account": "Water", "class": "1252 N 18th St", "type": "Expense",
     "notes": "1252 N 18th periodic water"},
    {"amount": 71.98, "account": "Water", "class": "1252 N 18th St", "type": "Expense",
     "notes": "1252 N 18th periodic water"},
]

# 2925 Master pre-stab utility routing (PCB account)
UTILITIES_2925_MASTER = {
    "philadelphia gas": {"account": "2925 Master Street", "type": "Asset", "class": None},
    "stormwater": {"account": "2925 Master Street", "type": "Asset", "class": None},
}

BANK_RULES = [
    # =========================================================
    # LOAN PAYMENTS - split via loan CSV parser
    # =========================================================
    {
        "name": "PCB Loan 9000854235 (1252 N 18th) - split via loan CSV",
        "match": {
            "any_description_contains": ["9000854235", "Transfer to 9000854235"],
            "amount_equals": 2030.82,
        },
        "account": "SPLIT_LOAN",
        "class": "9000854235",
        "type": "Liability",
        "notes": "Stabilized: principal → PCB Loan 9000854235, interest → Interest Expense + class 1252 N 18th St",
    },
    {
        "name": "PCB Loan 9001254757 (2925 Master) - interest-only capitalized",
        "match": {
            "any_description_contains": ["9001254757", "Transfer to 9001254757"],
        },
        "account": "SPLIT_LOAN",
        "class": "9001254757",
        "type": "Liability",
        "notes": "Pre-stab interest-only: full payment capitalized to 2925 Master Street asset",
    },

    # =========================================================
    # TD STORMWATER ($21.64 trio — handled by stormwater pass)
    # =========================================================
    {
        "name": "TD stormwater $21.64 (routed by stormwater pass)",
        "match": {
            "source_account_equals": "TD 3139011",
            "description_contains": "CITYOFPHILA",
            "amount_equals": 21.64,
        },
        "account": "STORMWATER_TD",
        "class": "STORMWATER_TD",
        "type": "Mixed",
        "notes": "Stormwater pass assigns to 1012 / 1008R / 1008-Veit per ROUTING table.",
    },

    # =========================================================
    # PCB WATER — 1252 N 18th (only stabilized rental on PCB)
    # =========================================================
    # Tightened to specific known recurring amounts to avoid sweeping up
    # any future non-1252 water bills paid via PCB. Add new amounts here
    # if 1252's water bill changes.
    {
        "name": "PCB water bill — 1252 N 18th St (recurring amounts)",
        "match": {
            "source_account_equals": "PCB 3869",
            "any_description_contains": ["CITYOFPHILA"],
            "amount_in": [-21.64, -59.33, -84.62, -71.98],
        },
        "account": "Water",
        "class": "1252 N 18th St",
        "type": "Expense",
        "notes": "PCB water at known 1252 N 18th amounts. New amounts must be added explicitly.",
    },

    # =========================================================
    # 2925 MASTER UTILITIES (PCB pre-stab capitalized)
    # =========================================================
    {
        "name": "Philadelphia Gas — 2925 Master (pre-stab capitalized)",
        "match": {
            "source_account_equals": "PCB 3869",
            "description_contains": "PHILADELPHIA GAS",
        },
        "account": "2925 Master Street",
        "class": None,
        "type": "Asset",
    },

    # =========================================================
    # RENTREDI DEPOSITS — 1252 N 18th (only stabilized rental)
    # =========================================================
    {
        "name": "RentRedi rent — 1252 N 18th",
        "match": {
            "description_contains": "RENTREDI",
        },
        "account": "Rental Income",
        "class": "1252 N 18th St",
        "type": "Income",
    },

    # =========================================================
    # ROBIN ELI P2P RENT — 1252 N 18th Unit A
    # =========================================================
    {
        "name": "Robin Eli P2P rent — 1252 N 18th Unit A",
        "match": {
            "description_contains": "ROBIN ELI",
        },
        "account": "Rental Income",
        "class": "1252 N 18th St",
        "type": "Income",
    },

    # =========================================================
    # MEMBER DRAW CHECKS — flagged for equity-cluster detection
    # =========================================================
    # Engine's equity_cluster pass detects $52,500 × 4 within 14 days and
    # assigns to members in order. Drafts 145, 1068, 135, 154 are the Q1 batch.
    {
        "name": "Member draw check $52,500",
        "match": {
            "amount_equals": -52500.00,
        },
        "account": "EQUITY_CLUSTER",
        "class": "EQUITY_CLUSTER",
        "type": "Equity",
        "notes": "Equity cluster pass assigns 4 draws → Steve/Josh/Gene/Boris in order.",
    },
]

ADMIN_RECLASSIFICATIONS = []

MANUAL_OVERRIDES_FILE_ID = None  # Use universal Manual Overrides Sheet 1kkM1nj2DirtnfeuJJJNE4ax1tr6yuRdV-Oy--DC5A8c

UNMATCHED_HANDLING = {
    "method": "review",
    "ask_threshold_amount": 0.00,
}

# Bank check patterns observed in property expense sheets when 10th Fairmount is paying
BANK_CHECK_PATTERNS = [
    "10th fairmount",
    "10th",
    "10F",
    "10thF",
    "echeck-bare",
]

# Entity names that disqualify a bare "echeck" match
BANK_CHECK_EXCLUDE_ENTITIES = [
    "vj assets", "vj",
    "sophia", "jbk", "cambria",
    "gj holdings", "veit", "phily properties",
    "g&j group", "gj group",
]

RETAIL_VENDOR_PATTERNS = [
    "peco", "philadelphia gas", "phila gas", "pgw",
    "cityofphila", "city of phila", "city of philadelphia",
    "phila dept rev", "phila26 li", "phila l&i",
    "foremost",
    "td bank", "penn community",
    "rentredi",
]
