"""
PCB CSV parser for Penn Community Bank online banking exports.

Replaces pcb_pdf.py as of Apr 30, 2026. PCB online banking offers CSV exports
which are vastly cleaner than parsing PDFs:
  - Date is a real date column
  - Description and Memo are separate columns (we combine them)
  - Amounts are split into Amount Debit / Amount Credit (we sign-correct)
  - Check Number is its own column (no regex extraction)
  - No (Rejected)/(Reverse) reversal-pair parsing needed; PCB exports them
    as separate transactions and the engine's reversal detection handles them
    via the existing logic.

Expected input format:
  Line 1: Account Name : Basic Business Checking,,,,,,,,
  Line 2: Account Number : 9001395494,,,,,,,,
  Line 3: Date Range : 01/01/2026-03/31/2026,,,,,,,,
  Line 4: Transaction Number,Date,Description,Memo,Amount Debit,Amount Credit,Balance,Check Number,Fees
  Line 5+: data rows

Filename convention: "<last4> <period>.csv" e.g. "5494 jan-march.csv"
The last 4 digits of the full account number (line 2) are used as the
source_account identifier throughout the engine (matches existing convention).
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import List, Optional


@dataclass
class Transaction:
    """Mirror of the engine's Transaction model. Adjust import if engine
    defines this elsewhere — keeping the shape identical for drop-in use."""
    txn_date: date
    description: str
    amount: Decimal           # signed: negative = debit, positive = credit
    source_account: str       # last 4 digits, e.g. "5494"
    check_number: Optional[str] = None
    memo: Optional[str] = None
    raw_description: Optional[str] = None  # original Description column only
    statement_period: Optional[str] = None  # e.g. "01/01/2026-03/31/2026"


# ---------------------------------------------------------------------------
# Header parsing
# ---------------------------------------------------------------------------

_ACCT_NUM_RE = re.compile(r"Account Number\s*:\s*(\d+)", re.IGNORECASE)
_DATE_RANGE_RE = re.compile(
    r"Date Range\s*:\s*(\d{2}/\d{2}/\d{4}-\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)


def _parse_header_lines(lines: List[str]) -> tuple[str, str]:
    """Return (last4_account, statement_period) from the metadata lines."""
    full_acct = None
    period = None
    for line in lines[:4]:
        if m := _ACCT_NUM_RE.search(line):
            full_acct = m.group(1)
        if m := _DATE_RANGE_RE.search(line):
            period = m.group(1)
    if not full_acct:
        raise ValueError("Could not find 'Account Number :' line in CSV header")
    if not period:
        raise ValueError("Could not find 'Date Range :' line in CSV header")
    return f"PCB {full_acct[-4:]}", period


# ---------------------------------------------------------------------------
# Field parsing helpers
# ---------------------------------------------------------------------------

def _parse_date(raw: str) -> date:
    """PCB uses M/D/YY format, e.g. '3/24/26'."""
    raw = raw.strip()
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Could not parse date {raw!r}")


def _parse_amount(debit: str, credit: str) -> Decimal:
    """Returns signed Decimal. Debit is negative (money out), Credit positive."""
    debit = (debit or "").strip()
    credit = (credit or "").strip()

    if debit and credit:
        # Shouldn't happen, but handle defensively
        raise ValueError(f"Row has both debit ({debit}) and credit ({credit})")
    if debit:
        # PCB writes debits already with leading minus, e.g. "-360"
        # Normalize so result is always negative
        d = Decimal(debit)
        return d if d < 0 else -d
    if credit:
        c = Decimal(credit)
        return c if c > 0 else -c
    raise ValueError("Row has neither debit nor credit amount")


def _combine_description(description: str, memo: str) -> str:
    """Combine Description + Memo into a single description string for rule matching.
    Format: 'Description | Memo' (or just 'Description' if memo is empty)."""
    description = (description or "").strip()
    memo = (memo or "").strip()
    if memo:
        return f"{description} | {memo}"
    return description


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def parse_pcb_csv(csv_path):
    """Parse a PCB online banking CSV export into a list of Transactions.

    The CSV has 3 metadata header lines, then a column header row, then data.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        all_lines = f.readlines()

    if len(all_lines) < 5:
        raise ValueError(f"CSV {csv_path} has fewer than 5 lines; malformed?")

    last4, period = _parse_header_lines(all_lines[:4])

    # Re-parse from the column-header row onward using csv module
    data_section = "".join(all_lines[3:])  # line 4 is the column header
    reader = csv.DictReader(data_section.splitlines())

    transactions = []
    for row_num, row in enumerate(reader, start=5):  # start=5 for human-friendly error msgs
        # Skip blank lines (some CSV exports have trailing empties)
        if not any((v or "").strip() for v in row.values()):
            continue

        try:
            txn_date = _parse_date(row["Date"])
            amount = _parse_amount(row.get("Amount Debit", ""), row.get("Amount Credit", ""))
            description = _combine_description(
                row.get("Description", ""),
                row.get("Memo", ""),
            )
            check_num = (row.get("Check Number") or "").strip() or None

            transactions.append(Transaction(
                txn_date=txn_date,
                description=description,
                amount=amount,
                source_account=last4,
                check_number=check_num,
                memo=(row.get("Memo") or "").strip() or None,
                raw_description=(row.get("Description") or "").strip() or None,
                statement_period=period,
            ))
        except Exception as e:
            raise ValueError(
                f"Error parsing row {row_num} of {csv_path.name}: {e}\n"
                f"Row data: {row}"
            ) from e

    return transactions


def parse_pcb_csv_directory(directory):
    """Parse all PCB CSVs in a directory and return a combined transaction list,
    sorted by date then by source account.

    Filenames must match pattern '<last4> <anything>.csv' (e.g. '5494 jan-march.csv').
    """
    directory = Path(directory)
    if not directory.exists() or not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    all_txns = []
    for csv_file in sorted(directory.glob("*.csv")):
        # Skip output CSVs and other non-PCB files by checking the filename
        # starts with a 4-digit account number.
        if not re.match(r"^\d{4}\s", csv_file.name):
            continue
        all_txns.extend(parse_pcb_csv(csv_file))

    all_txns.sort(key=lambda t: (t.txn_date, t.source_account))
    return all_txns


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python pcb_csv.py <csv_file_or_directory>")
        sys.exit(1)

    target = Path(sys.argv[1])
    if target.is_dir():
        txns = parse_pcb_csv_directory(target)
    else:
        txns = parse_pcb_csv(target)

    print(f"Parsed {len(txns)} transactions")
    print(f"Date range: {min(t.txn_date for t in txns)} to {max(t.txn_date for t in txns)}")
    print(f"Accounts:   {sorted({t.source_account for t in txns})}")
    print()
    print("First 5 transactions:")
    for t in txns[:5]:
        print(f"  {t.txn_date} {t.source_account} {t.amount:>12} {t.description[:80]}")
    print()
    print("Last 5 transactions:")
    for t in txns[-5:]:
        print(f"  {t.txn_date} {t.source_account} {t.amount:>12} {t.description[:80]}")
