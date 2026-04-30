"""
Loads Chase credit card transactions for the reconciliation engine.

Pipeline:
  1. Read Chase CSV exports (parsers/chase_csv.py)
  2. Convert to engine.Transaction objects
  3. Return engine-ready transactions

No reversal/pairing pass needed: Chase doesn't show the bounce/retry pattern
that PCB does. (If a Reversal type appears, we'll add pairing then.)

Statement credits arrive as Type='Adjustment' rows. They flow through to
the engine, where the existing 'STATEMENT CREDIT' admin reclassification
rule classifies them as Other Income. No parser-level transformation needed.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from reconcile.engine import Transaction as EngineTransaction
from reconcile.parsers.chase_csv import (
    Transaction as CsvTransaction,
    parse_chase_csv,
)


def _csv_to_engine(csv_txn: CsvTransaction) -> EngineTransaction:
    """Convert a parser-level Transaction (Decimal amounts, txn_date) into
    an engine-level Transaction (float amounts, date)."""
    return EngineTransaction(
        source_account=csv_txn.source_account,
        date=csv_txn.txn_date,
        description=csv_txn.description,
        amount=float(csv_txn.amount),
        raw_data={
            "txn_type": csv_txn.txn_type,
            "post_date": csv_txn.post_date.isoformat() if csv_txn.post_date else None,
            "category": csv_txn.category,
            "memo": csv_txn.memo,
            "source_parser": "chase_csv",
        },
    )


def load_chase_transactions(source):
    """Load Chase transactions from a CSV file or directory of CSVs.

    Returns a list of engine-ready Transaction objects, ready to feed to
    engine.reconcile() as the card_transactions parameter.

    If `source` is a directory, all *.csv files matching Chase format are
    loaded and combined. If `source` is a single file, just that one is loaded.
    """
    source = Path(source)

    if source.is_dir():
        all_engine_txns = []
        for csv_file in sorted(source.glob("*.csv")) + sorted(source.glob("*.CSV")):
            with csv_file.open("r", encoding="utf-8-sig") as f:
                first_line = f.readline().strip()
            if first_line.startswith("Card,") or first_line.startswith('"Card"'):
                csv_txns = parse_chase_csv(csv_file)
                all_engine_txns.extend(_csv_to_engine(t) for t in csv_txns)
        return all_engine_txns
    elif source.is_file():
        csv_txns = parse_chase_csv(source)
        return [_csv_to_engine(t) for t in csv_txns]
    else:
        raise FileNotFoundError(f"Source not found: {source}")


if __name__ == "__main__":
    import sys
    from collections import Counter, defaultdict

    if len(sys.argv) < 2:
        print("Usage: python -m reconcile.load_chase <csv_file_or_directory>")
        sys.exit(1)

    txns = load_chase_transactions(sys.argv[1])

    print(f"Loaded {len(txns)} engine-ready Chase transactions")
    if not txns:
        sys.exit(0)

    print(f"Date range: {min(t.date for t in txns)} to {max(t.date for t in txns)}")
    print()

    by_type = Counter(t.raw_data.get("txn_type") for t in txns)
    print("By type:")
    for typ, n in by_type.most_common():
        amount = sum(t.amount for t in txns if t.raw_data.get("txn_type") == typ)
        print(f"  {typ:<12}: {n:>4} txns  total ${amount:>12,.2f}")
    print()

    by_card = defaultdict(lambda: {"count": 0, "amount": 0.0})
    for t in txns:
        by_card[t.source_account]["count"] += 1
        by_card[t.source_account]["amount"] += t.amount
    print("By card:")
    for card in sorted(by_card.keys()):
        d = by_card[card]
        print(f"  {card}: {d['count']:>4} txns  total ${d['amount']:>12,.2f}")
    print()

    print("First 5 transactions (engine format):")
    for t in txns[:5]:
        print(f"  {t.date} {t.source_account:<16} ${t.amount:>10.2f}  {t.description[:60]}")
