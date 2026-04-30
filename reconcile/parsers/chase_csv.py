"""
Chase CSV parser for credit card transactions exported from Chase online banking.

Chase's CSV is cleaner than PCB's:
  - No metadata header rows; first line is the column header
  - Card column already shows last-4 of the sub-card (e.g., 2226, 3600, 7635)
  - Transaction Date and Post Date are separate fields
  - Description is a single column (no Memo to combine)
  - Amount is already sign-corrected (charges negative, credits positive)
  - Type column distinguishes Sale, Return, Payment, Reversal, Adjustment

Treatment by CSV Type:
  Sale         -> kept (will be classified as Construction Costs after
                  per-property allocation via expense sheets)
  Return       -> kept (offsets a prior Sale)
  Reversal     -> kept (paired with original by pairing.py to net to zero)
  Adjustment   -> kept (per rules doc, statement credits = Other Income)
  Payment      -> DROPPED (the offsetting autopay is already booked on
                  the PCB side as a 'CC Payment' to Chase liability;
                  keeping it here would double-count the event).

The parser does NOT filter by date or by statement cycle; it returns ALL
transactions. Period and cycle filtering is the engine/loader's job.
"""

from __future__ import annotations

import csv
import html
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import List, Optional


@dataclass
class Transaction:
    """Mirror of pcb_csv.Transaction for engine compatibility. The
    'source_account' here is the Chase sub-card identifier prefixed with
    'Chase Ink ' to match the rules file convention."""
    txn_date: date
    description: str
    amount: Decimal
    source_account: str          # e.g. "Chase Ink 2226"
    txn_type: str                # 'Sale', 'Return', 'Reversal', 'Adjustment'
    post_date: Optional[date] = None
    category: Optional[str] = None
    memo: Optional[str] = None


# Types we DROP entirely from the parsed output.
# Payments are already booked on the PCB side as CC Payment rows.
DROPPED_TYPES = {"Payment"}

# Recognized types (anything else triggers a warning)
KNOWN_TYPES = {"Sale", "Return", "Payment", "Reversal", "Adjustment"}


def _parse_date(raw):
    """Chase exports use either M/D/YY or MM/DD/YYYY. Try both."""
    raw = raw.strip()
    for fmt in ("%m/%d/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Could not parse date {raw!r}")


def _parse_amount(raw):
    """Chase amounts are pre-signed: charges negative, credits positive."""
    return Decimal(raw.strip())


def _normalize_card(raw):
    """Convert raw card number to engine-format identifier.
       '2226' -> 'Chase Ink 2226'  (matches rules file convention)
    """
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("Empty Card column")
    if raw.startswith("Chase Ink"):
        return raw
    return f"Chase Ink {raw}"


def parse_chase_csv(csv_path):
    """Parse a Chase CSV export into a list of Transaction objects.

    Drops 'Payment' rows (handled on PCB side).
    Returns transactions sorted by date then card.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    transactions = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=2):
            if not any((v or "").strip() for v in row.values()):
                continue

            txn_type = (row.get("Type") or "").strip()
            if txn_type in DROPPED_TYPES:
                continue
            if txn_type not in KNOWN_TYPES:
                print(f"WARN: Unknown Type {txn_type!r} on row {row_num}; "
                      f"keeping anyway. Description: {row.get('Description', '')!r}")

            try:
                txn_date = _parse_date(row["Transaction Date"])
                post_date_raw = (row.get("Post Date") or "").strip()
                post_date = _parse_date(post_date_raw) if post_date_raw else None
                amount = _parse_amount(row["Amount"])
                description = html.unescape((row.get("Description") or "").strip())
                category = (row.get("Category") or "").strip() or None
                memo = html.unescape((row.get("Memo") or "").strip()) or None
                source_account = _normalize_card(row.get("Card", ""))
            except Exception as e:
                raise ValueError(
                    f"Error parsing row {row_num} of {csv_path.name}: {e}\n"
                    f"Row: {row}"
                ) from e

            transactions.append(Transaction(
                txn_date=txn_date,
                description=description,
                amount=amount,
                source_account=source_account,
                txn_type=txn_type,
                post_date=post_date,
                category=category,
                memo=memo,
            ))

    transactions.sort(key=lambda t: (t.txn_date, t.source_account))
    return transactions


if __name__ == "__main__":
    import sys
    from collections import Counter, defaultdict

    if len(sys.argv) < 2:
        print("Usage: python chase_csv.py <csv_file>")
        sys.exit(1)

    txns = parse_chase_csv(sys.argv[1])
    print(f"Parsed {len(txns)} transactions (Payment rows dropped)")
    print(f"Date range: {min(t.txn_date for t in txns)} to {max(t.txn_date for t in txns)}")
    print()

    type_count = Counter(t.txn_type for t in txns)
    print("By type:")
    for typ, n in type_count.most_common():
        amount = sum((t.amount for t in txns if t.txn_type == typ), Decimal("0"))
        print(f"  {typ:<12}: {n:>4} txns  total ${amount:>12,.2f}")
    print()

    print("By card:")
    by_card = defaultdict(lambda: {"count": 0, "amount": Decimal("0")})
    for t in txns:
        by_card[t.source_account]["count"] += 1
        by_card[t.source_account]["amount"] += t.amount
    for card in sorted(by_card.keys()):
        d = by_card[card]
        print(f"  {card}: {d['count']:>4} txns  total ${d['amount']:>12,.2f}")
    print()

    print("First 5 transactions:")
    for t in txns[:5]:
        print(f"  {t.txn_date} {t.source_account:<16} {t.txn_type:<10} "
              f"{t.amount:>10}  {t.description[:60]}")
    print()

    print("Last 5 transactions:")
    for t in txns[-5:]:
        print(f"  {t.txn_date} {t.source_account:<16} {t.txn_type:<10} "
              f"{t.amount:>10}  {t.description[:60]}")
