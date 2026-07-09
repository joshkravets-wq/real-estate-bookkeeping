"""
Bank Credits & Debits sheet loader.

Reads the master ledger of non-Chase, non-payroll transactions across all
entities (Drive file ID 1l5ujV9j5EKd32_cHHHToCzDO-F1nXDh2). Used as Tier 3
of the Chase card matching workflow, and as Tier 1 (highest priority) for
unidentified bank transactions.

Sheet structure (6 columns, as of 2026-05-01):
    Date | Account | Description | Property | Amount | QB Account (Josh's Purposes)

  - "Account" column = the OWNING entity (GJ Holdings, Sophia Holdings, etc.).
    For paired transactions between entities, may use arrow notation
    (e.g., "Sophia -> G&J"). Amount is from the FIRST-named entity's
    perspective; loader matches on absolute amount.
  - "Property" column = property address (e.g., "5461 W Berks St"). May be blank.
  - "QB Account (Josh's Purposes)" = the QB account Josh decided to use.
    May be blank (engine should infer or flag for review).
  - Amount is signed.

Sheet has summary footer rows below the detail rows. Loader stops at
first row with empty Date.

Auto-classification logic (best-confidence path first):
  1. If QB Account column is populated AND validates against engine's known
     accounts registry -> use it directly. Property column gives the class.
     If QB Account is unknown (typo) -> flag for review.
  2. If Property column is populated AND keyword rules apply (RE tax, rent)
     -> infer QB account from rules, use Property as class.
  3. (Q1 2026 fallback only) If both columns blank, parse property and
     keyword from Description. Used to handle historical rows.
  4. Otherwise -> flag for review with the matched entry as evidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

from reconcile.drive_client import DriveClient


BANK_CREDITS_DEBITS_FILE_ID = "1l5ujV9j5EKd32_cHHHToCzDO-F1nXDh2"


# ============================================================================
# REGISTRIES (known-good QB accounts and properties)
# ============================================================================

# QB accounts the engine recognizes. Must mirror QB chart of accounts exactly.
# Adding a new one? Update both this and (where needed) rules/<entity>.py.
KNOWN_ACCOUNTS = {
    "Management Fee Income": {"type": "income", "takes_class": False},
    "Capital One Card Expense": {"type": "expense", "takes_class": False},
    "Chase Card Expense": {"type": "expense", "takes_class": False},
    "Health Insurance Expense": {"type": "expense", "takes_class": False},
    "Telephone Expense": {"type": "expense", "takes_class": False},
    "Taxes - Federal": {"type": "expense", "takes_class": False},
    "Transfer from closed TD account": {"type": "bank", "takes_class": False},
    "ASK": {"type": "asset", "takes_class": False},  # provisional/unidentified — resolve before year-end
    "Repairs & Maintenance": {"type": "expense", "takes_class": True},
    "Due to JBK Homes LLC": {"type": "liability", "takes_class": False},
    "Due from SJ Developers LLC": {"type": "asset", "takes_class": False},
    "Marketing Expense": {"type": "expense", "takes_class": False},
    "Office Expense": {"type": "expense", "takes_class": False},
    "Car Expense": {"type": "expense", "takes_class": False},
    "Loan from Steven Kravets": {"type": "liability", "takes_class": False},
    "Management Fees": {"type": "expense", "takes_class": True},
    "Licenses & Permits": {"type": "expense", "takes_class": True},
    "Internet Expense": {"type": "expense", "takes_class": True},
    "PCB Loan 9000743074": {"type": "liability", "takes_class": False},
    # Income
    "Construction Income": {"type": "income", "takes_class": False},
    "Rental Income": {"type": "income", "takes_class": True},
    "Other Income": {"type": "income", "takes_class": False},

    # COGS
    "Subcontractors Expense": {"type": "cogs", "takes_class": True},
    "Construction Costs": {"type": "cogs", "takes_class": True},

    # Operating Expenses
    "Tax Preparation Expense": {"type": "expense", "takes_class": False},
    "Liability Insurance Expense": {"type": "expense", "takes_class": False},
    "Software Expense": {"type": "expense", "takes_class": False},
    "Postage Expense": {"type": "expense", "takes_class": False},
    "Bank Service Charges": {"type": "expense", "takes_class": False},
    "Water Expense": {"type": "expense", "takes_class": True},
    "Gas Expense": {"type": "expense", "takes_class": True},
    "Taxes - Phila": {"type": "expense", "takes_class": True},

    # Current assets (Due from)
    "Due from Sophia Holdings": {"type": "asset", "takes_class": False},
    "Due from GJ Holdings LLC": {"type": "asset", "takes_class": False},
    "Due from JBK Homes": {"type": "asset", "takes_class": False},
    "Due from Cambria Group LLC": {"type": "asset", "takes_class": False},
    "Due from Veit LLC": {"type": "asset", "takes_class": False},
    "Due from Phily Properties LLC": {"type": "asset", "takes_class": False},

    # Bank accounts
    "PCB 5494": {"type": "bank", "takes_class": False},
    "PCB 5501": {"type": "bank", "takes_class": False},

    # Credit card liabilities
    "Chase Ink 3600": {"type": "liability", "takes_class": False},
    "Fay Loan 0000426433": {"type": "liability", "takes_class": False},
    "PCB Loan 9000798251": {"type": "liability", "takes_class": False},
    "PCB Loan 9000829048": {"type": "liability", "takes_class": False},
    "AMEX": {"type": "liability", "takes_class": False},

    # Equity
    "Steve Kravets Capital:Contribution": {"type": "equity", "takes_class": False},
    "Josh Kravets Capital:Contribution": {"type": "equity", "takes_class": False},
    "Gene Kravets Capital:Contribution": {"type": "equity", "takes_class": False},
    "Boris Capital:Contribution": {"type": "equity", "takes_class": False},
    "Steve Kravets Capital:Draws": {"type": "equity", "takes_class": False},
    "Josh Kravets Capital:Draw": {"type": "equity", "takes_class": False},
    "Gene Kravets Capital:Draws": {"type": "equity", "takes_class": False},
    "Boris Capital:Draw": {"type": "equity", "takes_class": False},

    # Gain/Loss
    "Gain on Sale of 2030 N Lawrence St": {"type": "income", "takes_class": False},

    # Insurance refund (Other Income); takes class for stabilized property refunds.
    # Pre-stab insurance refunds reduce property asset directly (no class).
    "Insurance Refund": {"type": "income", "takes_class": True},
}


# Property names also valid as account names (for pre-stab fixed assets).
KNOWN_PROPERTIES = [
    "5461 W Berks St", "5746 Grays Ave", "2563 E Elkhart St",
    "2139 N 7th St", "2143 N Palethorp St", "2925 Master St",
    "2030 N Lawrence St", "2672 Braddock Ave", "1934 N 3rd St",
    "2148 N 3rd St", "438 W Susquehanna St", "2411 N 3rd St",
    "2024 Wilder St", "2415 N 4th St", "2431 N 3rd St",
    "314 W Norris St", "1948 N Orianna St", "1252 N 18th St",
    "1012 Fairmount Ave", "1008R Fairmount", "1008 Fairmount Ave",
    "1010 Fairmount Ave", "2210 Amber St", "1430 N Marston St",
    "2505 Jefferson St", "2119 Hope St", "3435 Mercer St",
    "542 Edgley St", "943 N 43rd St", "6541 Edmund St",
    "1920 E Harold St", "2101 E Dauphin", "1745 N 29th", "507 W Dauphin St",
    "1948 N Orianna St", "2433 N 6th St", "7338 N 20th St",
    "2428 N Fairhill St",
]




# Street suffixes commonly omitted in casual entry
_STREET_SUFFIXES = ("st", "street", "ave", "avenue", "rd", "road", "ct", "court", "dr", "drive")


def _normalize_property(name):
    """Lowercase, strip trailing 'St'/'Ave'/etc for tolerant property matching."""
    if not name:
        return ""
    s = name.strip().lower()
    parts = s.split()
    while parts and parts[-1] in _STREET_SUFFIXES:
        parts.pop()
    return " ".join(parts)


def _match_property_loosely(name):
    """Return the canonical KNOWN_PROPERTIES name that matches `name` ignoring case + street suffix."""
    if not name:
        return None
    target = _normalize_property(name)
    if not target:
        return None
    for p in KNOWN_PROPERTIES:
        if _normalize_property(p) == target:
            return p
    return None

def is_known_account(name: str) -> bool:
    """Return True if name is a recognized QB account (including property fixed assets).
    Case-insensitive lookup."""
    if name is None:
        return False
    name_lower = name.strip().lower()
    return any(k.lower() == name_lower for k in KNOWN_ACCOUNTS) or \
           any(p.lower() == name_lower for p in KNOWN_PROPERTIES)


def account_type(name: str) -> Optional[str]:
    """Return the type of a known account ('income', 'expense', 'asset', etc.) or None.
    Case-insensitive lookup."""
    if name is None:
        return None
    name_lower = name.strip().lower()
    for k, v in KNOWN_ACCOUNTS.items():
        if k.lower() == name_lower:
            return v["type"]
    for p in KNOWN_PROPERTIES:
        if p.lower() == name_lower:
            return "fixed_asset"
    return None


def account_takes_class(name: str) -> bool:
    """Return True if this account requires a class. Properties as fixed assets do not.
    Case-insensitive lookup."""
    if name is None:
        return False
    name_lower = name.strip().lower()
    for k, v in KNOWN_ACCOUNTS.items():
        if k.lower() == name_lower:
            return v["takes_class"]
    return False  # Fixed assets named after property don't take class


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class BankCreditDebitEntry:
    """One row from the Bank Credits & Debits sheet."""
    row_num: int                # 1-indexed
    txn_date: date
    account_label: str          # "GJ Holdings", "Sophia -> G&J"
    description: str
    property: Optional[str]     # from Property column (or None)
    amount: float               # signed
    qb_account_josh: Optional[str]  # from "QB Account (Josh's Purposes)" column


@dataclass
class MatchSuggestion:
    """Auto-classification suggestion produced by interpret_match()."""
    qb_account: Optional[str]
    qb_class: Optional[str]
    confidence: str             # 'high', 'low', or 'none'
    reason: str                 # human-readable explanation


# ============================================================================
# LOADER
# ============================================================================

def load_entries(drive_client: Optional[DriveClient] = None) -> List[BankCreditDebitEntry]:
    """Fetch the sheet via Drive API and parse all detail rows."""
    client = drive_client or DriveClient()
    wb = client.fetch_spreadsheet(BANK_CREDITS_DEBITS_FILE_ID)
    sheet = wb.active

    entries: List[BankCreditDebitEntry] = []

    # Find header row.
    header_row = None
    for row_idx, row in enumerate(sheet.iter_rows(min_row=1, max_row=10, values_only=True), start=1):
        if row and row[0] == "Date":
            header_row = row_idx
            break

    if header_row is None:
        raise ValueError("Could not find header row in Bank Credits & Debits sheet")

    # Column indices (0-based, since values_only=True returns tuples)
    # Schema: Date(0) | Account(1) | Description(2) | Property(3) | Amount(4) | QB Account (5)
    COL_DATE, COL_ACCT, COL_DESC, COL_PROP, COL_AMOUNT, COL_QB = 0, 1, 2, 3, 4, 5

    for row_idx, row in enumerate(
        sheet.iter_rows(min_row=header_row + 1, values_only=True),
        start=header_row + 1,
    ):
        if row is None or row[COL_DATE] is None:
            # First blank row = end of detail rows
            break

        d = row[COL_DATE]
        account_label = row[COL_ACCT]
        description = row[COL_DESC] if len(row) > COL_DESC else None
        prop = row[COL_PROP] if len(row) > COL_PROP else None
        amount = row[COL_AMOUNT] if len(row) > COL_AMOUNT else None
        qb_acct_josh = row[COL_QB] if len(row) > COL_QB else None

        # Date parsing
        if isinstance(d, datetime):
            txn_date = d.date()
        elif isinstance(d, date):
            txn_date = d
        elif isinstance(d, str):
            try:
                txn_date = datetime.strptime(d.strip(), "%m/%d/%Y").date()
            except ValueError:
                print(f"WARN: row {row_idx} has unparseable date {d!r}; skipping")
                continue
        else:
            print(f"WARN: row {row_idx} has unexpected date type {type(d)}; skipping")
            continue

        # Amount parsing
        if isinstance(amount, str):
            cleaned = amount.replace("$", "").replace(",", "").replace("(", "-").replace(")", "")
            try:
                amount = float(cleaned)
            except ValueError:
                print(f"WARN: row {row_idx} has unparseable amount {amount!r}; skipping")
                continue
        elif amount is None:
            print(f"WARN: row {row_idx} has no amount; skipping")
            continue

        entries.append(BankCreditDebitEntry(
            row_num=row_idx,
            txn_date=txn_date,
            account_label=str(account_label or "").strip(),
            description=str(description or "").strip(),
            property=str(prop).strip() if prop else None,
            amount=float(amount),
            qb_account_josh=str(qb_acct_josh).strip() if qb_acct_josh else None,
        ))

    return entries


# ============================================================================
# MATCHING
# ============================================================================

def match_transaction(
    txn_date: date,
    txn_amount: float,
    entries: List[BankCreditDebitEntry],
    date_tolerance_days: int = 2,
    amount_tolerance: float = 1.00,
) -> List[BankCreditDebitEntry]:
    """Find Bank Credits & Debits entries that match a transaction.

    Matches on absolute amount (sheet may record from opposite-side perspective).
    """
    matches = []
    target_abs = abs(txn_amount)
    earliest = txn_date - timedelta(days=date_tolerance_days)
    latest = txn_date + timedelta(days=date_tolerance_days)

    for e in entries:
        if not (earliest <= e.txn_date <= latest):
            continue
        if abs(abs(e.amount) - target_abs) <= amount_tolerance:
            matches.append(e)

    return matches


# ============================================================================
# AUTO-CLASSIFICATION
# ============================================================================

def _find_property_in_text(text: str) -> Optional[str]:
    """Q1 fallback: parse property out of free-text Description.
    Returns canonical property address or None.
    """
    text_upper = text.upper()
    for prop in KNOWN_PROPERTIES:
        # Match number + main word (e.g. "5461 W Berks" matches "5461 W Berks St")
        parts = prop.split()
        if len(parts) >= 2:
            number = parts[0]
            if number not in text:
                continue
            # Find the distinctive street name (skip directional like W/N/E/S)
            for word in parts[1:]:
                if word.upper() in {"W", "N", "E", "S", "ST", "AVE", "RD", "CT"}:
                    continue
                if word.upper() in text_upper:
                    return prop
    return None


def interpret_match(entry: BankCreditDebitEntry) -> MatchSuggestion:
    """Decide what QB account/class to use for a matched sheet entry.

    Priority:
      1. QB Account column populated -> validate, use it
      2. Property column populated -> infer account from keyword rules
      3. Q1 fallback: parse property from description
      4. Flag for review
    """
    # Path 1: QB Account column populated by Josh
    if entry.qb_account_josh:
        qb = entry.qb_account_josh

        # Validate the account name itself
        if not is_known_account(qb):
            return MatchSuggestion(
                qb_account=None, qb_class=None,
                confidence="none",
                reason=f"QB Account {qb!r} not in known accounts registry. Possible typo. Add to KNOWN_ACCOUNTS or fix sheet.",
            )

        # Validate Property column too (if it would be needed for class)
        if account_takes_class(qb):
            if not entry.property:
                return MatchSuggestion(
                    qb_account=qb, qb_class=None,
                    confidence="low",
                    reason=f"QB Account {qb!r} requires a class but Property column is blank.",
                )
            canonical_prop = _match_property_loosely(entry.property)
            if not canonical_prop:
                return MatchSuggestion(
                    qb_account=qb, qb_class=entry.property,
                    confidence="low",
                    reason=f"Property {entry.property!r} not in KNOWN_PROPERTIES. Possible typo.",
                )
            return MatchSuggestion(
                qb_account=qb, qb_class=canonical_prop,
                confidence="high",
                reason=f"Josh decided: {qb} + class {canonical_prop}",
            )
        else:
            # Account does not take a class
            return MatchSuggestion(
                qb_account=qb, qb_class=None,
                confidence="high",
                reason=f"Josh decided: {qb} (no class)",
            )

    # Path 2: Property populated, no QB Account -> infer from keyword rules
    desc_upper = entry.description.upper()

    if entry.property:
        canonical_prop = _match_property_loosely(entry.property)
        if not canonical_prop:
            return MatchSuggestion(
                qb_account=None, qb_class=None,
                confidence="none",
                reason=f"Property {entry.property!r} not in KNOWN_PROPERTIES; cannot infer.",
            )
        # Use canonical name for downstream consistency
        entry_property_canonical = canonical_prop

        # RE tax keyword -> capitalize to property fixed asset
        if "RE TAX" in desc_upper or "REAL ESTATE TAX" in desc_upper:
            return MatchSuggestion(
                qb_account=entry.property, qb_class=None,
                confidence="high",
                reason=f"RE tax for {entry.property} (capitalize to fixed asset)",
            )

        # Rent keyword -> Rental Income with property class
        if "RENT" in desc_upper and "RENTAL LICENSE" not in desc_upper:
            return MatchSuggestion(
                qb_account="Rental Income", qb_class=entry.property,
                confidence="high",
                reason=f"Rent income for {entry.property}",
            )

        return MatchSuggestion(
            qb_account=None, qb_class=entry.property,
            confidence="low",
            reason=f"Property identified ({entry.property}) but no keyword rule applies; need QB account.",
        )

    # Path 3: Q1 fallback - parse property from description
    prop = _find_property_in_text(entry.description)
    if prop:
        if "RE TAX" in desc_upper or "REAL ESTATE TAX" in desc_upper:
            return MatchSuggestion(
                qb_account=prop, qb_class=None,
                confidence="high",
                reason=f"[Q1 fallback] RE tax for {prop} (parsed from description)",
            )
        if "RENT" in desc_upper and "RENTAL LICENSE" not in desc_upper:
            return MatchSuggestion(
                qb_account="Rental Income", qb_class=prop,
                confidence="high",
                reason=f"[Q1 fallback] Rent for {prop} (parsed from description)",
            )

    # Path 4: Nothing matched -> flag for review
    return MatchSuggestion(
        qb_account=None, qb_class=None,
        confidence="none",
        reason="No QB Account or Property in sheet; no keyword rule matched description.",
    )


# ============================================================================
# CLI smoke test
# ============================================================================

if __name__ == "__main__":
    print("Loading Bank Credits & Debits sheet from Drive...")
    entries = load_entries()
    print(f"Loaded {len(entries)} entries")
    print(f"Date range: {min(e.txn_date for e in entries)} to {max(e.txn_date for e in entries)}")
    print()

    # Show counts by Property/QB column population
    has_property = sum(1 for e in entries if e.property)
    has_qb = sum(1 for e in entries if e.qb_account_josh)
    print(f"Entries with Property column populated: {has_property}/{len(entries)}")
    print(f"Entries with QB Account column populated: {has_qb}/{len(entries)}")
    print()

    print("First 5 entries:")
    for e in entries[:5]:
        prop = e.property or '-'
        qb = e.qb_account_josh or '-'
        print(f"  row {e.row_num:>3} {e.txn_date} {e.account_label:<22} ${e.amount:>10,.2f}")
        print(f"          desc: {e.description[:60]}")
        print(f"          prop: {prop!r}  qb: {qb!r}")
    print()

    # Auto-classification breakdown
    print("Auto-classification results:")
    high = []
    low = []
    none = []
    for e in entries:
        s = interpret_match(e)
        if s.confidence == "high":
            high.append((e, s))
        elif s.confidence == "low":
            low.append((e, s))
        else:
            none.append((e, s))

    print(f"  High confidence: {len(high)}")
    print(f"  Low confidence:  {len(low)}")
    print(f"  No suggestion:   {len(none)}")
    print()

    # Show samples of each confidence level
    print(f"--- Samples (5 high confidence) ---")
    for e, s in high[:5]:
        print(f"  {e.txn_date} {e.account_label:<22} {e.description[:50]}")
        print(f"    -> account={s.qb_account}, class={s.qb_class}")
        print(f"    -> {s.reason}")
        print()

    print(f"--- Samples (5 review needed) ---")
    for e, s in none[:5]:
        print(f"  {e.txn_date} {e.account_label:<22} {e.description[:50]}")
        print(f"    -> {s.reason}")
        print()

    # Specific test: $1,973 Sophia reimbursement on 3/9
    from datetime import date as dt_date
    print("Match test: looking for $1,973 around 3/9/2026...")
    matches = match_transaction(dt_date(2026, 3, 9), 1973.00, entries)
    for m in matches:
        print(f"  Found: row {m.row_num} {m.txn_date} {m.account_label} ${m.amount}")
        print(f"         {m.description}")
        s = interpret_match(m)
        print(f"  Suggested: account={s.qb_account}, class={s.qb_class}, confidence={s.confidence}")
        print(f"  Reason:    {s.reason}")
