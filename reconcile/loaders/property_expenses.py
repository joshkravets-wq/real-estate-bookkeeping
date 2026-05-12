"""
Property expense sheet loader.

Reads a property's Google Sheet expense ledger via Drive API and parses
the date/amount/payee/payment-method columns. Used to match Chase card
transactions to specific properties for class assignment.

Sheet structure varies slightly across properties but typically:
    Date | Activity/Materials | Amount | Payee | Check #'s | Balance | ...

The loader finds columns by HEADER NAME (not position) so it tolerates
variations. The match function filters to rows where the payment method
column contains "Chase" (any case, any whitespace) before applying the
date+amount tolerance match.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import List, Optional

from reconcile.drive_client import DriveClient


HEADER_DATE = "date"
HEADER_DESC = "activity/materials"
HEADER_AMOUNT = "amount"
HEADER_PAYEE = "payee"
HEADER_PAYMENT = "check #'s"


def _norm_header(s):
    if not s:
        return ""
    s = str(s).lower().strip()
    s = s.replace("\u2019", "'")
    s = re.sub(r"\s+", " ", s)
    return s


HEADER_ALIASES = {
    HEADER_DATE: {"date"},
    HEADER_DESC: {"activity/materials", "activity / materials", "activity"},
    HEADER_AMOUNT: {"amount", "$ amount", "cost"},
    HEADER_PAYEE: {"payee", "vendor", "to"},
    HEADER_PAYMENT: {"check #'s", "check #s", "check #", "check#", "payment", "method"},
}


@dataclass
class PropertyExpenseEntry:
    property_name: str
    row_num: int
    txn_date: date
    description: str
    amount: float
    payee: str
    payment_method: str
    raw: dict = field(default_factory=dict)

    def is_chase(self):
        return "chase" in (self.payment_method or "").lower()


def _find_header_columns(header_row):
    found = {}
    for col_idx, raw in enumerate(header_row):
        normalized = _norm_header(raw)
        for canonical, aliases in HEADER_ALIASES.items():
            if normalized in aliases:
                if canonical not in found:
                    found[canonical] = col_idx
    required = [HEADER_DATE, HEADER_AMOUNT, HEADER_PAYEE, HEADER_PAYMENT]
    missing = [c for c in required if c not in found]
    if missing:
        raise ValueError(
            f"Required columns not found in header: {missing}. "
            f"Got header: {header_row!r}"
        )
    return found


def _parse_date(raw, default_year=2026):
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    if not isinstance(raw, str):
        return None
    s = raw.strip().rstrip("/")
    if not s:
        return None
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    for fmt in ("%m/%d",):
        try:
            d = datetime.strptime(s, fmt).date()
            return d.replace(year=default_year)
        except ValueError:
            continue
    return None


def _parse_amount(raw):
    if raw is None or raw == "":
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if not isinstance(raw, str):
        return None
    s = str(raw).strip()
    if not s:
        return None
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    s = s.replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def load_property_entries(property_name, file_id, drive_client=None, default_year=2026):
    client = drive_client or DriveClient()
    wb = client.fetch_spreadsheet(file_id)
    sheet = wb.active

    # Find the header row by looking for multiple expected headers in the same row.
    # Required: "date" + at least one of {"amount", "payee", "activity/materials"}.
    # This discriminates real ledger headers from category lookup tables that
    # might have a "Date" column without other matches.
    header_row = None
    header_row_num = None
    for row_idx, row in enumerate(
        sheet.iter_rows(min_row=1, max_row=200, values_only=True), start=1
    ):
        if not row:
            continue
        normalized = [_norm_header(c) for c in row]
        has_date = any(n == HEADER_DATE for n in normalized)
        has_other = any(
            n in HEADER_ALIASES.get(HEADER_AMOUNT, set()) or
            n in HEADER_ALIASES.get(HEADER_PAYEE, set()) or
            n in HEADER_ALIASES.get(HEADER_DESC, set())
            for n in normalized
        )
        if has_date and has_other:
            header_row = row
            header_row_num = row_idx
            break

    if header_row is None:
        raise ValueError(
            f"Could not find header row in {property_name} (file {file_id}). "
            f"Looked at first 200 rows for 'Date' + amount/payee/activity. "
            f"Sheet may need restructuring."
        )

    cols = _find_header_columns(header_row)
    desc_col = cols.get(HEADER_DESC)

    entries = []
    skipped_unparseable = 0
    consecutive_bad = 0
    BAD_ROW_THRESHOLD = 50  # stop after this many consecutive non-parseable rows

    for row_idx, row in enumerate(
        sheet.iter_rows(min_row=header_row_num + 1, values_only=True),
        start=header_row_num + 1,
    ):
        if not row or all(c is None or (isinstance(c, str) and not c.strip()) for c in row):
            # Fully blank row - reset consecutive counter and skip
            consecutive_bad = 0
            continue

        date_raw = row[cols[HEADER_DATE]] if cols[HEADER_DATE] < len(row) else None
        amount_raw = row[cols[HEADER_AMOUNT]] if cols[HEADER_AMOUNT] < len(row) else None

        txn_date = _parse_date(date_raw, default_year=default_year)
        amount = _parse_amount(amount_raw)

        if txn_date is None:
            # Bad row (couldn't parse date). Skip but track for early termination.
            consecutive_bad += 1
            if consecutive_bad >= BAD_ROW_THRESHOLD:
                break
            continue

        if amount is None:
            consecutive_bad += 1
            skipped_unparseable += 1
            if consecutive_bad >= BAD_ROW_THRESHOLD:
                break
            continue

        # Good row - reset bad counter
        consecutive_bad = 0

        payee = row[cols[HEADER_PAYEE]] if cols[HEADER_PAYEE] < len(row) else ""
        payment = row[cols[HEADER_PAYMENT]] if cols[HEADER_PAYMENT] < len(row) else ""
        desc = ""
        if desc_col is not None and desc_col < len(row):
            desc = row[desc_col] or ""

        entries.append(PropertyExpenseEntry(
            property_name=property_name,
            row_num=row_idx,
            txn_date=txn_date,
            description=str(desc).strip(),
            amount=float(amount),
            payee=str(payee or "").strip(),
            payment_method=str(payment or "").strip(),
            raw={"row": row},
        ))

    if skipped_unparseable:
        print(f"  [{property_name}] skipped {skipped_unparseable} rows with unparseable amounts")

    return entries


def match_property_transaction(
    txn_date,
    txn_amount,
    entries,
    amount_tolerance=1.00,
    date_tolerance_days=14,
    chase_only=True,
    payment_method_patterns=None,
    exclude_other_entities=None,
):
    """Find expense sheet entries matching a transaction.

    Args:
        chase_only: If True, only match rows where payment_method contains 'chase'.
        payment_method_patterns: List of substrings (case-insensitive) any of which
            must appear in payment_method. Used for bank-check matching.
            If both chase_only and payment_method_patterns are set,
            payment_method_patterns takes precedence.
    """
    target_abs = abs(txn_amount)
    earliest = txn_date - timedelta(days=date_tolerance_days)
    latest = txn_date + timedelta(days=date_tolerance_days)

    matches = []
    excludes_lower = [s.lower() for s in (exclude_other_entities or [])]
    for e in entries:
        # Apply payment method filter (patterns OR chase)
        if payment_method_patterns is not None:
            pm = (e.payment_method or "").lower()
            matched_pattern = False
            for p in payment_method_patterns:
                p_lower = p.lower()
                if p_lower == "echeck-bare":
                    # Special token: matches "echeck" if no other entity is mentioned
                    if "echeck" in pm and not any(x in pm for x in excludes_lower):
                        matched_pattern = True
                        break
                elif p_lower in pm:
                    matched_pattern = True
                    break
            if not matched_pattern:
                continue
        elif chase_only and not e.is_chase():
            continue

        if not (earliest <= e.txn_date <= latest):
            continue
        if abs(abs(e.amount) - target_abs) <= amount_tolerance:
            matches.append(e)
    return matches


if __name__ == "__main__":
    print("Loading 5746 Grays Ave expense sheet...")
    entries = load_property_entries(
        property_name="5746 Grays Ave",
        file_id="1kKNKkzX9zJTKjCkx4DYHoJ1ZSZs97pWQNps3xTmG99U",
    )
    print(f"Loaded {len(entries)} entries")
    if not entries:
        print("(no entries)")
        import sys
        sys.exit(0)

    print(f"Date range: {min(e.txn_date for e in entries)} to {max(e.txn_date for e in entries)}")
    print()

    chase_count = sum(1 for e in entries if e.is_chase())
    print(f"Chase rows: {chase_count}/{len(entries)}")
    print()

    print("First 5 entries:")
    for e in entries[:5]:
        chase = "[CHASE]" if e.is_chase() else "       "
        print(f"  row {e.row_num:>3} {e.txn_date} {chase} ${e.amount:>9,.2f}  {e.payee[:30]:<30}  {e.payment_method[:20]}")

    print()
    print("Last 5 entries:")
    for e in entries[-5:]:
        chase = "[CHASE]" if e.is_chase() else "       "
        print(f"  row {e.row_num:>3} {e.txn_date} {chase} ${e.amount:>9,.2f}  {e.payee[:30]:<30}  {e.payment_method[:20]}")

    print()
    print("=" * 70)
    print("Match tests against actual Q1 2026 Chase transactions:")
    print("=" * 70)

    test_cases = [
        ("Chase Sale (should match)", date(2026, 2, 5), -1953.00, "Tile and two vanities"),
        ("Chase Sale (should match)", date(2026, 1, 22), -4848.00, "Floor (Washington brother)"),
        ("Chase Sale (should match)", date(2026, 1, 26), -2136.00, "Doors and molding"),
        ("Chase Refund (should match)", date(2026, 3, 19), 1208.00, "Floor return"),
        ("Should NOT match (off date)", date(2026, 2, 5), -99999.00, "huge wrong amount"),
    ]

    for label, d, amt, desc in test_cases:
        matches = match_property_transaction(d, amt, entries, chase_only=True)
        print()
        print(f"{label}: ${amt} on {d} ({desc})")
        if matches:
            for m in matches:
                print(f"  match: row {m.row_num} {m.txn_date} ${m.amount:,.2f} {m.payee[:30]} - {m.description[:30]}")
        else:
            print(f"  no matches")
