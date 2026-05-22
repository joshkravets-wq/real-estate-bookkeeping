"""
TD Bank online-banking CSV parser.

Format observed (10th Fairmount LLC, Q1 2026):
    Date,Bank RTN,Account Number,Transaction Type,Description,Debit,Credit,Check Number,Account Running Balance

Notes:
- Dates appear as M/D/YY (e.g., "3/12/26")
- Debit and Credit are positive numbers; sign determined by which column is populated
- Description has trailing whitespace; normalize
- Transaction Type values seen: DEBIT, DEP, DIRECTDEBIT, CHECK (likely)
- Check Number column may be blank
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import List

from reconcile.engine import Transaction  # adjust if your Transaction lives elsewhere


def _parse_date(s: str) -> datetime:
    s = s.strip()
    # Handle "3/12/26" and "03/12/2026"
    for fmt in ("%m/%d/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Could not parse TD date: {s!r}")


def _norm_account(account_number: str) -> str:
    """TD account 4303139011 → 'TD 3139011' to match rules convention."""
    acct = account_number.strip()
    if acct.startswith("430"):
        return f"TD {acct[3:]}"
    return f"TD {acct}"


def parse_td_csv(path: Path | str) -> List[Transaction]:
    """Parse a TD Bank CSV export into Transaction objects."""
    path = Path(path)
    transactions: List[Transaction] = []

    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date_str = (row.get("Date") or "").strip()
            if not date_str:
                continue

            try:
                date = _parse_date(date_str)
            except ValueError:
                continue

            debit_str = (row.get("Debit") or "").strip()
            credit_str = (row.get("Credit") or "").strip()

            try:
                debit = float(debit_str) if debit_str else 0.0
                credit = float(credit_str) if credit_str else 0.0
            except ValueError:
                continue

            # TD presents debits as positive numbers; signed_amount is negative for debits
            if debit and not credit:
                amount = -abs(debit)
            elif credit and not debit:
                amount = abs(credit)
            else:
                # both empty or both populated — skip
                continue

            description = (row.get("Description") or "").strip()
            txn_type = (row.get("Transaction Type") or "").strip()
            check_num = (row.get("Check Number") or "").strip()
            account_num = (row.get("Account Number") or "").strip()

            # Build a description that includes type for downstream rules
            full_description = description
            if txn_type and txn_type.lower() not in description.lower():
                full_description = f"{txn_type} {description}".strip()

            source_account = _norm_account(account_num)

            txn = Transaction(
                date=date,
                description=full_description,
                amount=amount,
                source_account=source_account,
                raw_data={
                    "raw_description": description,
                    "transaction_type": txn_type,
                    "check_number": check_num,
                    "running_balance": (row.get("Account Running Balance") or "").strip(),
                    "source_file": str(path.name),
                },
            )
            transactions.append(txn)

    # Sort ascending by date (TD exports are reverse-chronological)
    transactions.sort(key=lambda t: t.date)
    return transactions
