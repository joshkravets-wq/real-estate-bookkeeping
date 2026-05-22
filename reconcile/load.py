"""
Loads PCB bank transactions for the reconciliation engine.

Pipeline:
  1. Read PCB CSV exports from a directory (parsers/pcb_csv.py)
  2. Net out reversal/NSF artifacts (pairing.py)
  3. Convert clean Transaction objects into engine.Transaction objects
  4. Return engine-ready transactions + audit log

The engine itself stays unaware of bank-specific quirks. Other parsers
(Chase, AMEX) will plug in here too once they exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Tuple

from reconcile.engine import Transaction as EngineTransaction
from reconcile.parsers.pcb_csv import (
    Transaction as CsvTransaction,
    parse_pcb_csv,
    parse_pcb_csv_directory,
)
from reconcile.pairing import pair_reversals, PairingResult


@dataclass
class AuditEntry:
    """Record of a transaction the loader dropped before classification.
    Useful for audit trails and debugging unexpected reconciliation results.
    """
    txn_date: date
    source_account: str
    amount: float
    description: str
    reason: str


def _csv_to_engine(csv_txn: CsvTransaction) -> EngineTransaction:
    """Convert a parser-level Transaction (Decimal amounts, txn_date) into
    an engine-level Transaction (float amounts, date). Extra fields like
    memo, raw_description, and statement_period are preserved in raw_data
    so rules can reach for them if they need to."""
    return EngineTransaction(
        source_account=csv_txn.source_account,
        date=csv_txn.txn_date,
        description=csv_txn.description.replace(" | ", " "),
        amount=float(csv_txn.amount),
        raw_data={
            "memo": csv_txn.memo,
            "raw_description": csv_txn.raw_description,
            "statement_period": csv_txn.statement_period,
            "check_number": csv_txn.check_number,
            "source_parser": "pcb_csv",
        },
    )


def load_pcb_transactions(
    source: Path | str,
) -> Tuple[List[EngineTransaction], List[AuditEntry], PairingResult]:
    """Load PCB transactions from a CSV file or directory of CSVs, run
    reversal/NSF pairing, and return engine-ready Transaction objects
    plus an audit log.

    Returns:
        (engine_transactions, audit_log, pairing_result)
        - engine_transactions: feed these to engine.reconcile() as
          bank_transactions
        - audit_log: list of dropped-pair AuditEntry records, useful for
          generating audit reports alongside the Processor CSV
        - pairing_result: full PairingResult object with the original
          parser-level transactions (kept + dropped) and audit notes
    """
    source = Path(source)

    if source.is_dir():
        raw_txns = parse_pcb_csv_directory(source)
    elif source.is_file():
        raw_txns = parse_pcb_csv(source)
    else:
        raise FileNotFoundError(f"Source not found: {source}")

    pairing = pair_reversals(raw_txns)

    # Convert kept transactions to engine format
    engine_txns = [_csv_to_engine(t) for t in pairing.kept]

    # Build audit log from dropped transactions
    audit_log = [
        AuditEntry(
            txn_date=t.txn_date,
            source_account=t.source_account,
            amount=float(t.amount),
            description=t.description,
            reason=reason,
        )
        for t, reason in pairing.dropped
    ]

    return engine_txns, audit_log, pairing


# ---------------------------------------------------------------------------
# CLI for quick verification
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m reconcile.load <csv_file_or_directory>")
        sys.exit(1)

    engine_txns, audit_log, pairing = load_pcb_transactions(sys.argv[1])

    print(f"Loaded {len(engine_txns)} engine-ready transactions")
    print(f"Audit log: {len(audit_log)} dropped pairs")
    print()
    print("=" * 70)
    print("AUDIT NOTES (from pairing)")
    print("=" * 70)
    for note in pairing.audit_notes:
        print(f"  {note}")
    print()
    print("=" * 70)
    print(f"ENGINE-READY TRANSACTIONS ({len(engine_txns)})")
    print("=" * 70)
    print(f"{'Date':<12} {'Acct':<6} {'Amount':>12}  Description")
    print("-" * 70)
    for t in engine_txns:
        print(f"{t.date.isoformat():<12} {t.source_account:<6} "
              f"{t.amount:>12.2f}  {t.description[:60]}")

    # Sanity check: conservation of money
    raw_total = sum(float(t.amount) for t, _ in pairing.dropped) + sum(
        t.amount for t in engine_txns
    )
    print()
    print(f"Sum of all amounts (kept + dropped): {raw_total:.2f}")
    print("(Should equal sum of raw bank transactions for the period)")


def _td_csv_to_engine(td_txn):
    """Convert a TD parser-level Transaction into an EngineTransaction.

    The TD parser already returns Transaction objects that match the engine's
    shape (date, description, amount, source_account, raw_data). We just need
    to ensure raw_data has a source_parser tag.
    """
    raw_data = dict(td_txn.raw_data or {})
    raw_data.setdefault("source_parser", "td_csv")

    return EngineTransaction(
        source_account=td_txn.source_account,
        date=td_txn.date,
        description=td_txn.description,
        amount=float(td_txn.amount),
        raw_data=raw_data,
    )


def load_td_transactions(source):
    """Load TD Bank transactions from a CSV file or directory of CSVs.

    Returns a list of engine-ready EngineTransaction objects. TD CSVs have no
    NSF/reversal artifacts that need pairing (unlike PCB), so this is a
    simpler load path than load_pcb_transactions.
    """
    from reconcile.parsers.td_csv import parse_td_csv

    source = Path(source)
    raw_txns = []

    if source.is_dir():
        for csv_path in sorted(source.glob("*.csv")):
            raw_txns.extend(parse_td_csv(csv_path))
    elif source.is_file():
        raw_txns = parse_td_csv(source)
    else:
        raise FileNotFoundError(f"TD source not found: {source}")

    return [_td_csv_to_engine(t) for t in raw_txns]

