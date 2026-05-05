"""
Reconciliation Engine

Takes:
  - A list of transactions (from PDFs/CSVs/Plaid)
  - An entity's rules
  - Property metadata
  - A checks CSV (transcribed by Claude from check images)
  - Property expense sheets (from Drive)

Produces:
  - A classified transaction list (with QB Account + Class for each)
  - A list of items needing user input (unmatched, ambiguous, "ASK" rules)
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional


@dataclass
class Transaction:
    """A raw transaction from a bank/credit card statement."""
    source_account: str
    date: date
    description: str
    amount: float
    raw_data: dict = field(default_factory=dict)

    qb_account: Optional[str] = None
    payee: Optional[str] = None
    qb_class: Optional[str] = None
    transaction_type: Optional[str] = None
    classified_by: Optional[str] = None
    needs_review: bool = False
    review_reason: Optional[str] = None

    @property
    def is_check(self) -> bool:
        return "Check" in self.description and any(c.isdigit() for c in self.description)

    @property
    def check_number(self) -> Optional[str]:
        if not self.is_check:
            return None
        import re
        m = re.search(r'Check\s+(\d+)', self.description)
        return m.group(1) if m else None


@dataclass
class CheckRecord:
    """A check transcribed from PDF by Claude."""
    account: str
    check_num: str
    date: date
    amount: float
    payee: str
    memo: str
    qb_account: str
    qb_class: str


@dataclass
class ExpenseSheetEntry:
    """A row from a property's expense sheet in Drive."""
    property_name: str
    date: date
    amount: float
    description: str
    card: str
    raw_row: dict = field(default_factory=dict)


@dataclass
class ReviewItem:
    """An item the engine couldn't auto-classify; needs user input."""
    transaction: Transaction
    reason: str
    suggested_account: Optional[str] = None
    suggested_class: Optional[str] = None


# ============================================================================
# RULE MATCHING
# ============================================================================

def matches_rule(txn: Transaction, rule: dict) -> bool:
    match = rule.get("match", {})

    if "description_contains" in match:
        if match["description_contains"].lower() not in txn.description.lower():
            return False

    if "any_description_contains" in match:
        descriptions = match["any_description_contains"]
        if not any(d.lower() in txn.description.lower() for d in descriptions):
            return False

    if "amount_equals" in match:
        if abs(abs(txn.amount) - match["amount_equals"]) > 0.01:
            return False

    if "is_check" in match:
        if match["is_check"] != txn.is_check:
            return False

    if "is_reversed_in_statement" in match:
        is_reversed = txn.raw_data.get("is_reversed", False)
        if match["is_reversed_in_statement"] != is_reversed:
            return False

    return True


def apply_bank_rules(txn: Transaction, rules: list) -> Optional[dict]:
    for rule in rules:
        if matches_rule(txn, rule):
            return rule
    return None


# ============================================================================
# EXPENSE SHEET MATCHING (for credit card transactions)
# ============================================================================

def match_to_expense_sheets(
    txn: Transaction,
    expense_sheets: dict,
    config: dict
):
    amount_tol = config.get("amount_tolerance", 1.00)
    date_tol_days = config.get("date_tolerance_days", 7)
    round_amounts = config.get("round_amounts", True)

    txn_amount = abs(txn.amount)
    if round_amounts:
        txn_amount_search_low = round(txn_amount) - amount_tol
        txn_amount_search_high = round(txn_amount) + amount_tol
    else:
        txn_amount_search_low = txn_amount - amount_tol
        txn_amount_search_high = txn_amount + amount_tol

    date_low = txn.date - timedelta(days=date_tol_days)
    date_high = txn.date + timedelta(days=date_tol_days)

    matches = []

    tier_1 = config.get("tier_1_properties", [])
    for prop_name in tier_1:
        sheet = expense_sheets.get(prop_name, [])
        for entry in sheet:
            entry_amount = round(entry.amount) if round_amounts else entry.amount
            if (txn_amount_search_low <= entry_amount <= txn_amount_search_high
                and date_low <= entry.date <= date_high):
                matches.append((prop_name, entry))
        if matches:
            break

    if not matches and config.get("search_all_properties_after_tier_1", True):
        for prop_name, sheet in expense_sheets.items():
            if prop_name in tier_1:
                continue
            for entry in sheet:
                entry_amount = round(entry.amount) if round_amounts else entry.amount
                if (txn_amount_search_low <= entry_amount <= txn_amount_search_high
                    and date_low <= entry.date <= date_high):
                    matches.append((prop_name, entry))

    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        return None
    else:
        return None


# ============================================================================
# ADMIN RECLASSIFICATION
# ============================================================================

def find_admin_reclassification(txn: Transaction, reclassifications: list) -> Optional[dict]:
    desc_upper = txn.description.upper()
    for rule in reclassifications:
        vendor_pattern = rule.get("vendor_contains", "").upper()
        if vendor_pattern and vendor_pattern in desc_upper:
            return rule
    return None


# ============================================================================
# CHECK LOOKUP
# ============================================================================

def lookup_check(txn: Transaction, checks: list) -> Optional[CheckRecord]:
    if not txn.is_check:
        return None
    check_num = txn.check_number
    if not check_num:
        return None

    for check in checks:
        if check.check_num == check_num and check.account == txn.source_account:
            if abs(check.amount - abs(txn.amount)) < 0.01:
                return check
    return None


# ============================================================================
# MAIN ENGINE
# ============================================================================

def reconcile(
    bank_transactions: list,
    card_transactions: list,
    checks: list,
    expense_sheets: dict,
    rules_module,
):
    review_items = []
    all_txns = []

    # Bank transactions
    for txn in bank_transactions:
        if txn.is_check:
            check = lookup_check(txn, checks)
            if check:
                txn.qb_account = check.qb_account
                txn.qb_class = check.qb_class
                txn.transaction_type = "Expense"
                txn.classified_by = f"checks_csv (check #{check.check_num})"
                all_txns.append(txn)
                continue
            else:
                review_items.append(ReviewItem(
                    transaction=txn,
                    reason=f"Check #{txn.check_number} not found in checks CSV",
                ))
                continue

        rule = apply_bank_rules(txn, rules_module.BANK_RULES)
        if rule:
            if rule["type"] == "Transfer":
                # Determine the other bank account by looking at entity config
                bank_accounts = rules_module.ENTITY.get("bank_accounts", [])
                other_accounts = [a for a in bank_accounts if a != txn.source_account]
                txn.qb_account = other_accounts[0] if other_accounts else rule["account"]

                # Rewrite description to be unambiguous about direction
                if txn.amount > 0:
                    direction = f"Transfer from {txn.qb_account} -> {txn.source_account}"
                else:
                    direction = f"Transfer from {txn.source_account} -> {txn.qb_account}"
                txn.description = direction
            else:
                txn.qb_account = rule["account"]

            if rule.get("class") == "ASK":
                review_items.append(ReviewItem(
                    transaction=txn,
                    reason=f"Rule '{rule['name']}' matched but class needs confirmation",
                    suggested_account=txn.qb_account,
                ))
                continue
            else:
                txn.qb_class = rule.get("class")

            txn.transaction_type = rule["type"]
            txn.classified_by = rule["name"]
            all_txns.append(txn)
        else:
            review_items.append(ReviewItem(
                transaction=txn,
                reason="No matching rule",
            ))

    # Card transactions
    for txn in card_transactions:
        match_result = match_to_expense_sheets(
            txn,
            expense_sheets,
            rules_module.CARD_MATCHING
        )

        if match_result:
            property_name, entry = match_result
            txn.qb_account = "Construction Costs"
            txn.qb_class = property_name
            txn.transaction_type = "Expense"
            txn.classified_by = f"expense_sheet:{property_name} ({entry.description[:30]})"
            all_txns.append(txn)
            continue

        admin_rule = find_admin_reclassification(txn, rules_module.ADMIN_RECLASSIFICATIONS)
        if admin_rule:
            txn.qb_account = admin_rule["account"]

            if admin_rule.get("class") == "DATE_DEPENDENT":
                date_str = txn.date.isoformat()
                date_map = admin_rule.get("date_class_map", {})
                if date_str in date_map:
                    txn.qb_class = date_map[date_str]
                else:
                    review_items.append(ReviewItem(
                        transaction=txn,
                        reason=f"WEFILMPHILLY date {date_str} not in date map; which property?",
                        suggested_account=admin_rule["account"],
                    ))
                    continue
            else:
                txn.qb_class = admin_rule.get("class")

            txn.transaction_type = "Reclass"
            txn.classified_by = f"admin:{admin_rule['vendor_contains']}"
            all_txns.append(txn)
            continue

        unmatched_config = rules_module.UNMATCHED_HANDLING
        if abs(txn.amount) >= unmatched_config.get("ask_threshold_amount", 100.00):
            review_items.append(ReviewItem(
                transaction=txn,
                reason=f"Unmatched card transaction over ${unmatched_config['ask_threshold_amount']:.0f} threshold",
            ))
        else:
            txn.qb_account = "Construction Costs"
            txn.qb_class = "PROPORTIONAL_DISTRIBUTION"
            txn.classified_by = "unmatched_proportional"
            all_txns.append(txn)

    return all_txns, review_items
