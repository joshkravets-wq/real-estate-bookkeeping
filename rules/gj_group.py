"""
G&J Group LLC -- Reconciliation Rules

Architecture:
  G&J Group is a wholly-owned general contractor service company. Owns NO properties.

Money IN:
  - From owning entities (GJ Holdings, 10th Fairmount, Cambria Group, Sophia Holdings)
    => Construction Income (revenue, no class)
  - Reimbursements for expenses fronted
    => Due from [Entity] (current asset, NOT income)

Money OUT:
  - Bank checks/ACH to subcontractors
    => Subcontractors Expense (COGS) + property class
  - Credit card payments (Chase, AMEX)
    => Construction Costs (COGS) + property class via reconciliation split
  - General overhead (tax prep, insurance, software, postage)
    => respective expense accounts, no class

Inter-account transfers (5494 <-> 5501): no P&L impact.
"""

ENTITY = {
    "name": "G&J Group LLC",
    "ein": "61-1570442",
    "address": "1363 Buttonwood Dr, Southampton PA 18966",
    "bank_accounts": ["PCB 5494", "PCB 5501"],
    "credit_cards": ["Chase Ink 3600", "Chase Ink 2226", "Chase Ink 7635", "AMEX"],
    "income_account": "Construction Income",
    "cogs_basis": "cash",
}

# ============================================================================
# BANK TRANSACTION RULES (applied in order, first match wins)
# ============================================================================

BANK_RULES = [
    # Inter-account transfers (no P&L impact)
    {
        "name": "5494 <-> 5501 transfer",
        "match": {
            "any_description_contains": ["Transfer between Gj accounts", "Transfer btw GJ", "Transfer 5501 to 5494", "Transfer between GJ"],
        },
        "account": "PCB 5501",
        "type": "Transfer",
        "notes": "No P&L impact, just bank-to-bank movement",
    },

    # Bank fees
    {
        "name": "NSF charge (kept)",
        "match": {
            "description_contains": "Insufficient Funds Charge",
            "is_reversed_in_statement": False,
        },
        "account": "Bank Service Charges",
        "type": "Expense",
    },

    # Credit card autopays
    {
        "name": "Chase autopay",
        "match": {"description_contains": "CHASE CREDIT CRD"},
        "account": "Chase Ink 3600",
        "type": "CC Payment",
        "notes": "Pays Chase 3600/2226/7635 bundled. Per-property allocation done via card reconciliation split.",
    },
    {
        "name": "AMEX autopay",
        "match": {"description_contains": "AMEX EPAYMENT"},
        "account": "AMEX",
        "type": "CC Payment",
        "notes": "Per-property allocation by Chase ratios until AMEX statements available.",
    },

    # Specific known reimbursements (must come BEFORE generic Sophia income rule)
    {
        "name": "Sophia 2139 N 7th insurance reimbursement",
        "match": {
            "description_contains": "2139 N 7th",
            "amount_equals": 1973.00,
        },
        "account": "Due from Sophia Holdings",
        "type": "Asset",
        "notes": "G&J fronted insurance for Sophia Holdings",
    },

    # Income from owning entities (generic rules)
    {
        "name": "GJ Holdings deposit",
        "match": {"any_description_contains": ["GJ Holdings", "GJ holding", "GJ hold", "gj hold"]},
        "account": "Construction Income",
        "type": "Income",
    },
    {
        "name": "10th Fairmount deposit",
        "match": {"any_description_contains": ["10thF", "10F", "10th Fair"]},
        "account": "Construction Income",
        "type": "Income",
    },
    {
        "name": "Sophia Holdings deposit",
        "match": {
            "any_description_contains": ["Sophia", "9000856207"],
        },
        "account": "Construction Income",
        "type": "Income",
        "notes": "Generic Sophia deposit. Reimbursements have specific rules above.",
    },

    # Subcontractor checks - matched via Checks CSV (Claude transcribes from PDFs)
    {
        "name": "Check (look up in Checks CSV)",
        "match": {"is_check": True},
        "account": "Subcontractors Expense",
        "type": "Expense",
        "class_from": "checks_csv",
    },

    # ACH payments to subcontractors
    {
        "name": "MCM LTD ACH (subcontractor materials)",
        "match": {"description_contains": "MCM LTD"},
        "account": "Subcontractors Expense",
        "class": "ASK",
        "type": "Expense",
        "notes": "Q1 2026: all MCM ACH went to 5461 W Berks St. Verify each.",
    },
]

# ============================================================================
# CARD MATCHING METHODOLOGY
# ============================================================================

CARD_MATCHING = {
    "amount_tolerance": 1.00,
    "date_tolerance_days": 7,
    "round_amounts": True,
    "tier_1_properties": [
        "5461 W Berks St",
        "5746 Grays Ave",
        "2563 E Elkhart St",
        "2139 N 7th St",
        "2143 N Palethorp St",
        "2925 Master St",
        "2030 N Lawrence St",
    ],
    "search_all_properties_after_tier_1": True,
    "bank_credits_debits_sheet": "1l5ujV9j5EKd32_cHHHToCzDO-F1nXDh2",
}

# ============================================================================
# ADMIN RECLASSIFICATIONS
# Applied AFTER card-to-property matching, BEFORE final aggregation.
# ============================================================================

ADMIN_RECLASSIFICATIONS = [
    # Tax Preparation
    {"vendor_contains": "TAX1099.COM", "account": "Tax Preparation Expense", "class": None},
    {"vendor_contains": "INTUIT", "account": "Tax Preparation Expense", "class": None,
     "notes": "Includes QuickBooks subscriptions"},

    # Insurance
    {"vendor_contains": "AMMODERN", "account": "Liability Insurance Expense", "class": None},
    {"vendor_contains": "GBLI", "account": "Liability Insurance Expense", "class": None},

    # Software
    {"vendor_contains": "ONLINECHECKWRITER", "account": "Software Expense", "class": None},

    # Postage
    {"vendor_contains": "USPS", "account": "Postage Expense", "class": None},

    # Property-specific admin items
    {"vendor_contains": "ENGINEER RESERVE", "account": "Construction Costs", "class": "2672 Braddock Ave"},
    {"vendor_contains": "PHILA L&I", "account": "Construction Costs", "class": "2672 Braddock Ave"},
    {"vendor_contains": "PHILA REV EZ-PAY", "account": "Construction Costs", "class": "2672 Braddock Ave"},
    {"vendor_contains": "CITY OF PHILADELPHIA", "account": "Construction Costs", "class": "2672 Braddock Ave"},
    {"vendor_contains": "PGW", "account": "Construction Costs", "class": "5746 Grays Ave",
     "notes": "PGW = Philadelphia Gas Works -> Grays Ave"},

    # WEFILMPHILLY photos -- date-dependent classification
    {"vendor_contains": "WEFILMPHILLY", "account": "Construction Costs", "class": "DATE_DEPENDENT",
     "date_class_map": {
         "2025-12-23": "2143 N Palethorp St",
         "2026-01-15": "2030 N Lawrence St",
         "2026-02-12": "2563 E Elkhart St",
     },
     "notes": "Property listing photos. Map by exact date; ASK if date not in map."},

    # Paid-in-error: Ambric Technology was actually JBK Homes' charge
    {"vendor_contains": "AMBRIC", "account": "Due from JBK Homes", "class": None,
     "notes": "Paid in error for JBK Homes. Refund expected April 2026."},

    # Statement credits -> Other Income (NOT netted against expenses)
    {"vendor_contains": "STATEMENT CREDIT", "account": "Other Income", "class": None,
     "notes": "Chase rewards/credits go to Other Income, not netted against Construction Costs."},
]

# ============================================================================
# AMEX ALLOCATION (until AMEX statements arrive)
# ============================================================================

AMEX_ALLOCATION = {
    "method": "chase_property_ratios",
    "fallback_message": "AMEX statements not yet available. AMEX charges allocated using Chase property ratios.",
}

# ============================================================================
# MANUAL OVERRIDES
# ============================================================================

MANUAL_OVERRIDES = [
    {
        "card_transaction": {"date": "2025-12-22", "amount": 929.03, "description_contains": "Home Depot"},
        "match_to": {"property": "2563 E Elkhart St", "expense_sheet_entry": "12/22 $923 Lumber, exterior door, other"},
        "approved_by": "Josh",
        "approved_session": "2026-04-28",
        "notes": "Was $6 off Elkhart 12/22 $923. Manually overridden after Josh approval.",
    },
]

# ============================================================================
# UNMATCHED ITEM HANDLING
# ============================================================================

UNMATCHED_HANDLING = {
    "method": "proportional_distribution",
    "ask_threshold_amount": 100.00,
}
