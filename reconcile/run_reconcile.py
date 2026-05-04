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
from reconcile.load_chase import load_chase_transactions
from reconcile.loaders.bank_credits_debits import (
    load_entries as load_bank_credits_entries,
    match_transaction as match_bank_credits,
    interpret_match as interpret_bank_credits_match,
)
from reconcile.output import write_engine_output


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
    parser.add_argument(
        "--period",
        required=True,
        help="Reporting period label (e.g. 'Jan-Mar 2026')",
    )
    parser.add_argument(
        "--output-dir",
        default="./output",
        help="Directory to write Processor CSV + Review.txt (default: ./output)",
    )
    parser.add_argument(
        "--chase-csv",
        default=None,
        help="Path to Chase CSV export (single file). Optional; omit to skip card classification.",
    )
    parser.add_argument(
        "--no-bank-credits",
        action="store_true",
        help="Skip the Bank Credits & Debits sheet matching pass.",
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
    # Load Chase if provided
    if args.chase_csv:
        print(f"Loading Chase transactions from {args.chase_csv}...")
        card_txns = load_chase_transactions(args.chase_csv)
        print(f"  {len(card_txns)} Chase transactions")
        print()
    else:
        card_txns = []
        print("No --chase-csv provided; skipping card classification")
        print()

    classified, review_items = reconcile(
        bank_transactions=bank_txns,
        card_transactions=card_txns,
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

    # 6.5 Post-process: match review-queue items against Bank Credits & Debits sheet
    if not args.no_bank_credits and review_items:
        print()
        print("=" * 90)
        print("BANK CREDITS & DEBITS PASS")
        print("=" * 90)
        try:
            print("Loading Bank Credits & Debits sheet from Drive...")
            bcd_entries = load_bank_credits_entries()
            print(f"  Loaded {len(bcd_entries)} entries")
        except Exception as e:
            print(f"  WARNING: Could not load Bank Credits & Debits sheet: {e}")
            bcd_entries = None

        if bcd_entries:
            from reconcile.loaders.bank_credits_debits import account_type
            type_map = {
                "income": "Income", "expense": "Expense", "cogs": "Expense",
                "asset": "Asset", "liability": "Liability", "bank": "Bank",
                "fixed_asset": "Asset", "equity": "Equity",
            }
            promoted = 0
            annotated = 0
            unmatched = 0
            still_review = []
            for item in review_items:
                txn = item.transaction
                matches = match_bank_credits(txn.date, txn.amount, bcd_entries)
                if not matches:
                    unmatched += 1
                    still_review.append(item)
                    continue
                if len(matches) == 1:
                    entry = matches[0]
                    suggestion = interpret_bank_credits_match(entry)
                    if suggestion.confidence == "high":
                        txn.qb_account = suggestion.qb_account
                        txn.qb_class = suggestion.qb_class
                        acct_type = account_type(suggestion.qb_account)
                        txn.transaction_type = type_map.get(acct_type, "Expense")
                        txn.classified_by = (
                            f"bank_credits_debits row {entry.row_num}: {suggestion.reason}"
                        )
                        classified.append(txn)
                        promoted += 1
                    else:
                        item.reason = (
                            f"{item.reason} | "
                            f"BCD row {entry.row_num}: {entry.description[:50]} "
                            f"(${entry.amount:.2f}, {entry.account_label}). "
                            f"Suggestion: {suggestion.reason}"
                        )
                        item.suggested_account = suggestion.qb_account
                        item.suggested_class = suggestion.qb_class
                        still_review.append(item)
                        annotated += 1
                else:
                    rows_str = ", ".join(f"row {m.row_num}" for m in matches)
                    item.reason = (
                        f"{item.reason} | "
                        f"BCD ambiguous: {len(matches)} matching entries ({rows_str})"
                    )
                    still_review.append(item)
                    annotated += 1

            review_items = still_review
            print()
            print(f"  Promoted to classified: {promoted}")
            print(f"  Annotated with BCD evidence: {annotated}")
            print(f"  No BCD match (unchanged): {unmatched}")
            print()
            print(f"Updated counts:")
            print(f"  Classified: {len(classified)}")
            print(f"  Review queue: {len(review_items)}")

    # 7. Write Processor CSV + Review.txt
    print()
    print("=" * 90)
    print("WRITING OUTPUTS")
    print("=" * 90)
    paths = write_engine_output(
        classified_transactions=classified,
        review_items=review_items,
        entity_name=rules_module.ENTITY.get("name", args.entity),
        period=args.period,
        output_dir=args.output_dir,
        checks_csv=None,
    )
    for label, path in paths.items():
        print(f"  {label}: {path}")


if __name__ == "__main__":
    main()
