"""
End-to-end reconciliation driver.

Pulls PCB bank CSVs, runs pairing, loads rules, and runs the engine's
classification logic. For now this is bank-only (no Chase/AMEX statement
parsers, no check images, no Drive expense sheets yet).

Usage:
    python -m reconcile.run_reconcile --entity gj_group --pcb-dir <path>

Output: prints classification results + review queue. Does not yet write
a Processor CSV — that comes after we verify classification works.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

from reconcile.engine import reconcile
from reconcile.load import load_pcb_transactions


def main():
    parser = argparse.ArgumentParser(description="Run reconciliation engine")
    parser.add_argument(
        "--entity",
        required=True,
        help="Entity rules module name (e.g. 'gj_group')",
    )
    parser.add_argument(
        "--pcb-dir",
        required=True,
        help="Directory containing PCB CSV exports",
    )
    args = parser.parse_args()

    # 1. Load and pair PCB transactions
    print(f"Loading PCB transactions from {args.pcb_dir}...")
    bank_txns, audit_log, pairing = load_pcb_transactions(args.pcb_dir)
    print(f"  {len(bank_txns)} engine-ready transactions")
    print(f"  {len(audit_log)} dropped pairs (audit trail preserved)")
    print()

    # 2. Load rules module
    print(f"Loading rules: rules.{args.entity}")
    try:
        rules_module = importlib.import_module(f"rules.{args.entity}")
    except ImportError as e:
        print(f"ERROR: Could not import rules.{args.entity}: {e}")
        sys.exit(1)
    print(f"  ENTITY: {rules_module.ENTITY.get('name', '?')}")
    print(f"  Bank rules: {len(rules_module.BANK_RULES)}")
    print()

    # 3. Run engine (bank-only path; empty placeholders for the rest)
    print("Running reconcile()...")
    classified, review_items = reconcile(
        bank_transactions=bank_txns,
        card_transactions=[],   # No Chase/AMEX parser yet
        checks=[],              # No check image transcription yet
        expense_sheets={},      # No Drive sheet loader yet
        rules_module=rules_module,
    )
    print(f"  Classified: {len(classified)}")
    print(f"  Review queue: {len(review_items)}")
    print()

    # 4. Show classified transactions
    print("=" * 90)
    print(f"CLASSIFIED ({len(classified)})")
    print("=" * 90)
    print(f"{'Date':<12} {'Acct':<6} {'Amount':>12}  {'Type':<10} {'QB Account':<28} {'Class':<22}")
    print("-" * 90)
    for t in classified:
        print(
            f"{t.date.isoformat():<12} {t.source_account:<6} "
            f"{t.amount:>12.2f}  "
            f"{(t.transaction_type or '?'):<10} "
            f"{(t.qb_account or '?'):<28} "
            f"{(t.qb_class or ''):<22}"
        )

    # 5. Show review queue
    print()
    print("=" * 90)
    print(f"REVIEW QUEUE ({len(review_items)})")
    print("=" * 90)
    if not review_items:
        print("  (empty)")
    for r in review_items:
        t = r.transaction
        print(
            f"  {t.date.isoformat()} {t.source_account} "
            f"{t.amount:>12.2f}  {t.description[:55]}"
        )
        print(f"      reason: {r.reason}")
        if r.suggested_account:
            print(f"      suggested account: {r.suggested_account}")
        if r.suggested_class:
            print(f"      suggested class:   {r.suggested_class}")

    # 6. Totals by transaction type (excludes Transfers from P&L)
    print()
    print("=" * 90)
    print("TOTALS BY TYPE")
    print("=" * 90)
    from collections import defaultdict
    by_type = defaultdict(float)
    for t in classified:
        by_type[t.transaction_type or "Unclassified"] += t.amount
    for txn_type in sorted(by_type.keys()):
        print(f"  {txn_type:<20} ${by_type[txn_type]:>15,.2f}")
    print()

    # P&L summary (Income + Expense only; excludes Transfer, CC Payment, Asset, Reclass)
    pnl_types = {"Income", "Expense"}
    pnl_total = sum(amount for t, amount in by_type.items() if t in pnl_types)
    print(f"  P&L (Income + Expense only): ${pnl_total:>15,.2f}")
    print()

    # Sanity check: transfers should net to zero
    transfer_net = by_type.get("Transfer", 0.0)
    if abs(transfer_net) > 0.01:
        print(f"  WARNING: Transfers do not net to zero (${transfer_net:.2f}) - review pairing")
    else:
        print(f"  Transfers net to zero: OK")

    # Conservation check: classified + review_items + dropped pairs should sum to raw bank total
    classified_total = sum(t.amount for t in classified)
    review_total = sum(r.transaction.amount for r in review_items)
    print(f"\n  Classified total:  ${classified_total:>15,.2f}")
    print(f"  Review queue total: ${review_total:>15,.2f}")
    print(f"  Combined:          ${classified_total + review_total:>15,.2f}")


if __name__ == "__main__":
    main()
