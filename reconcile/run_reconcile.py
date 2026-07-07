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
from reconcile.load import load_pcb_transactions, load_td_transactions
from reconcile.load_chase import load_chase_transactions
from reconcile.loaders.bank_credits_debits import (
    account_type,
    load_entries as load_bank_credits_entries,
    match_transaction as match_bank_credits,
    interpret_match as interpret_bank_credits_match,
)
from reconcile.loaders.property_expenses import (
    load_property_entries,
    match_property_transaction,
)
from reconcile.loaders.manual_overrides import (
    load_overrides,
    find_override,
    get_off_bank_journals,
)

import re as _prop_re_mod
_PROP_RE = _prop_re_mod.compile(r'^\d+\s')
from rules.properties_registry import ACTIVE_RENO_FILE_IDS, MANUAL_OVERRIDES_FILE_ID
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
        "--td-csv",
        default=None,
        help="Path to TD Bank CSV (single file) or directory. Optional; for entities banking at TD in addition to PCB.",
    )
    parser.add_argument(
        "--no-bank-credits",
        action="store_true",
        help="Skip the Bank Credits & Debits sheet matching pass.",
    )
    parser.add_argument(
        "--no-property-sheets",
        action="store_true",
        help="Skip the property expense sheet matching pass.",
    )
    parser.add_argument(
        "--no-manual-overrides",
        action="store_true",
        help="Skip the manual overrides pass.",
    )
    parser.add_argument(
        "--no-proportional-distribution",
        action="store_true",
        help="Skip proportional distribution of unmatched items.",
    )
    parser.add_argument(
        "--distribute-all-review-items",
        action="store_true",
        help="One-shot: move ALL review queue items into PROPORTIONAL_DISTRIBUTION before the distribution pass. Use sparingly; usually you want to handle review items individually.",
    )
    parser.add_argument(
        "--no-loan-splits",
        action="store_true",
        help="Skip the loan payments split pass",
    )
    parser.add_argument(
        "--no-water-ranking",
        action="store_true",
        help="Skip the water ranking pass",
    )
    parser.add_argument(
        "--no-gas-peco-split",
        action="store_true",
        help="Skip the gas/PECO 50/50 split pass",
    )
    parser.add_argument(
        "--no-rentredi",
        action="store_true",
        help="Skip the RentRedi rental income split pass",
    )
    parser.add_argument(
        "--distribute-amex",
        action="store_true",
        help="Distribute AMEX autopay totals across properties using Chase ratios. Use when AMEX statements are not available (e.g., card cancelled).",
    )
    args = parser.parse_args()

    # 1. Load and pair PCB transactions
    print(f"Loading PCB transactions from {args.pcb_dir}...")
    bank_txns, audit_log, pairing = load_pcb_transactions(args.pcb_dir)
    print(f"  {len(bank_txns)} engine-ready PCB transactions")
    print(f"  {len(audit_log)} dropped pairs (audit trail preserved)")

    # Optionally load TD transactions (no pairing needed for TD)
    if args.td_csv:
        print(f"Loading TD transactions from {args.td_csv}...")
        td_txns = load_td_transactions(args.td_csv)
        print(f"  {len(td_txns)} engine-ready TD transactions")
        bank_txns = bank_txns + td_txns
    else:
        print("No --td-csv provided; PCB-only")
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

    # 6.3 Post-process: apply manual overrides FIRST (highest priority)
    # Each override row is an explicit, audited accounting decision that
    # supersedes all engine logic. Applies to both classified and review items.
    if not args.no_manual_overrides:
        print()
        print("=" * 90)
        print("MANUAL OVERRIDES PASS")
        print("=" * 90)
        try:
            print("Loading Manual Overrides sheet from Drive...")
            overrides = load_overrides(MANUAL_OVERRIDES_FILE_ID)
            print(f"  Loaded {len(overrides)} override rows")
        except Exception as e:
            print(f"  WARNING: Could not load manual overrides: {e}")
            overrides = []

        if overrides:
            applied_to_classified = 0
            applied_to_review = 0
            still_review_after_overrides = []
            used_overrides = set()  # track row_nums to prevent same override matching multiple txns

            # Type mapping from account_type() result to QB Type column.
            _type_map = {"income": "Income", "expense": "Expense", "cogs": "Expense",
                         "asset": "Asset", "fixed_asset": "Asset", "liability": "Liability",
                         "bank": "Bank", "equity": "Equity"}

            # Apply to already-classified transactions (overwrite if matched)
            for txn in classified:
                ov = find_override(txn, overrides, used_overrides)
                if ov:
                    txn.qb_account = ov.qb_account
                    txn.qb_class = ov.qb_class
                    if getattr(ov, 'payee', ''):
                        txn.payee = ov.payee
                    _acct_type = account_type(ov.qb_account)
                    txn.transaction_type = _type_map.get(_acct_type, "Expense")
                    # Property-address accounts (e.g. '2110 E Cambria St') are
                    # capitalized asset accounts, not expenses. account_type()
                    # only knows registered accounts, so patch the fallback.
                    if txn.transaction_type == "Expense" and _PROP_RE.match(ov.qb_account or ""):
                        txn.transaction_type = "Asset"
                    txn.classified_by = (
                        f"manual_override[row {ov.row_num}]: "
                        f"{ov.notes[:50]}" if ov.notes else
                        f"manual_override[row {ov.row_num}]"
                    )
                    applied_to_classified += 1

            # Apply to review-queue items (promote to classified if matched)
            for item in review_items:
                txn = item.transaction
                ov = find_override(txn, overrides, used_overrides)
                if ov:
                    txn.qb_account = ov.qb_account
                    txn.qb_class = ov.qb_class
                    if getattr(ov, 'payee', ''):
                        txn.payee = ov.payee
                    _acct_type = account_type(ov.qb_account)
                    txn.transaction_type = _type_map.get(_acct_type, "Expense")
                    # Property-address accounts (e.g. '2110 E Cambria St') are
                    # capitalized asset accounts, not expenses. account_type()
                    # only knows registered accounts, so patch the fallback.
                    if txn.transaction_type == "Expense" and _PROP_RE.match(ov.qb_account or ""):
                        txn.transaction_type = "Asset"
                    txn.classified_by = (
                        f"manual_override[row {ov.row_num}]: "
                        f"{ov.notes[:50]}" if ov.notes else
                        f"manual_override[row {ov.row_num}]"
                    )
                    classified.append(txn)
                    applied_to_review += 1
                else:
                    still_review_after_overrides.append(item)

            review_items = still_review_after_overrides
            print()
            print(f"  Overrode classified items: {applied_to_classified}")
            print(f"  Promoted review items: {applied_to_review}")

            # Emit off-bank journal rows as synthetic classified transactions.
            # These have no bank counterpart (e.g., sale-clearing journals).
            off_bank_journals = get_off_bank_journals(overrides)
            if off_bank_journals:
                from reconcile.engine import Transaction as _Transaction
                emitted = 0
                for ov in off_bank_journals:
                    _acct_type = account_type(ov.qb_account)
                    ttype = _type_map.get(_acct_type, "Expense")
                    classified.append(_Transaction(
                        source_account=ov.account,
                        date=ov.txn_date,
                        description=ov.notes or ov.description_match or "Off-bank journal entry",
                        amount=float(ov.amount),
                        qb_account=ov.qb_account,
                        qb_class=ov.qb_class or "",
                        transaction_type=ttype,
                        classified_by=(
                            f"manual_override[row {ov.row_num}, off-bank]: "
                            f"{ov.notes[:50]}" if ov.notes else
                            f"manual_override[row {ov.row_num}, off-bank]"
                        ),
                    ))
                    emitted += 1
                print(f"  Off-bank journal entries emitted: {emitted}")

            print()
            print(f"Updated counts:")
            print(f"  Classified: {len(classified)}")
            print(f"  Review queue: {len(review_items)}")

    # 6.4 Post-process: match Chase review-queue items against property expense sheets
    if not args.no_property_sheets and review_items:
        print()
        print("=" * 90)
        print("PROPERTY EXPENSE SHEETS PASS (Chase + Bank checks)")
        print("=" * 90)
        try:
            print("Loading property expense sheets from Drive...")
            # Property file IDs come from the entity's rules module if available
            # (rules_module.PROPERTIES); fall back to ACTIVE_RENO_FILE_IDS for G&J Group.
            entity_props = getattr(rules_module, "PROPERTIES", None)
            if entity_props:
                property_file_ids = {
                    name: cfg.get("expense_sheet")
                    for name, cfg in entity_props.items()
                    if cfg.get("expense_sheet")
                }
            else:
                property_file_ids = dict(ACTIVE_RENO_FILE_IDS)

            property_entries = {}
            for prop_name, file_id in property_file_ids.items():
                try:
                    entries = load_property_entries(prop_name, file_id)
                    chase_count = sum(1 for e in entries if e.is_chase())
                    property_entries[prop_name] = entries
                    print(f"  {prop_name}: {len(entries)} entries ({chase_count} chase)")
                except Exception as e:
                    print(f"  {prop_name}: FAIL ({e})")
                    property_entries[prop_name] = []
        except Exception as e:
            print(f"  WARNING: Could not load property sheets: {e}")
            property_entries = None

        if property_entries:
            promoted = 0
            ambiguous = 0
            unmatched = 0
            still_review_after_property = []

            # Bank check matching patterns - sourced from rules module per entity.
            # Each entity has its own bank check labeling convention seen in expense sheets.
            DEFAULT_GJ_GROUP_PATTERNS = [
                "g&j group", "gj group", "g&j grp", "gj grp",
                "g&j 5494", "gj 5494", "g&j group494", "gj group494",
            ]
            GJ_BANK_PATTERNS = getattr(rules_module, "BANK_CHECK_PATTERNS", DEFAULT_GJ_GROUP_PATTERNS)

            for item in review_items:
                txn = item.transaction
                src_acct = (txn.source_account or "").lower()

                # Property expense entries represent money spent ON a property.
                # Bank deposits (positive amounts) can't pay for property work,
                # so don't try to match deposits against expense sheets.
                if txn.amount > 0:
                    still_review_after_property.append(item)
                    continue

                # Determine payment method patterns based on transaction source
                if "chase" in src_acct:
                    pmt_patterns = None  # Use chase_only fallback
                    use_chase = True
                elif "pcb" in src_acct:
                    pmt_patterns = GJ_BANK_PATTERNS
                    use_chase = False
                else:
                    # Unknown source - skip
                    still_review_after_property.append(item)
                    continue

                # Search across all property sheets
                all_matches = []
                for prop_name, entries in property_entries.items():
                    matches = match_property_transaction(
                        txn.date, txn.amount, entries,
                        chase_only=use_chase,
                        payment_method_patterns=pmt_patterns,
                        exclude_other_entities=getattr(rules_module, "BANK_CHECK_EXCLUDE_ENTITIES", []),
                    )
                    for m in matches:
                        all_matches.append((prop_name, m))

                if not all_matches:
                    unmatched += 1
                    still_review_after_property.append(item)
                    continue

                # Check if all matches are within the same property (still safe to auto-promote)
                unique_props = set(p for p, _ in all_matches)
                if len(unique_props) == 1:
                    # All matches in same property - take first match
                    prop_name = list(unique_props)[0]
                    entry = all_matches[0][1]
                    # Auto-promote: tag transaction with property class
                    txn.qb_class = prop_name
                    if not txn.payee and getattr(entry, 'payee', None):
                        txn.payee = entry.payee
                    # Determine QB account based on transaction source:
                    #   Chase card charge -> Construction Costs (per CHASE CARD METHODOLOGY)
                    #   Bank check -> Subcontractors Expense (per G&J GROUP architecture)
                    # Determine pre-stab vs stabilized treatment from the rules module
                    properties_cfg = getattr(rules_module, "PROPERTIES", {})
                    prop_cfg = properties_cfg.get(prop_name, {})
                    is_pre_stab = prop_cfg.get("status") == "pre-stab"

                    if "chase" in src_acct:
                        # Chase card - always Construction Costs (G&J Group flow)
                        if not txn.qb_account:
                            txn.qb_account = "Construction Costs"
                        if not txn.transaction_type:
                            txn.transaction_type = "Expense"
                    elif is_pre_stab:
                        # Bank check at pre-stab property - capitalize to property asset
                        # (regardless of expense type; pre-stab capitalizes everything)
                        txn.qb_account = prop_name
                        txn.qb_class = ""
                        txn.transaction_type = "Asset"
                    else:
                        # Bank check at stabilized property - route by expense type
                        # based on patterns in the matched expense sheet row.
                        entry_desc = (getattr(entry, "description", "") or "").lower()
                        entry_payee = (getattr(entry, "payee", "") or "").lower()
                        combined = f"{entry_desc} {entry_payee}"

                        if "tax" in entry_desc or "phila dept rev" in combined:
                            txn.qb_account = "Taxes - Phila"
                            txn.transaction_type = "Expense"
                        elif any(k in combined for k in ("insurance", "foremost", "homesite", "policy", "premium")):
                            txn.qb_account = "Insurance Expense"
                            txn.transaction_type = "Expense"
                        elif "water" in combined or "stormwater" in combined or "cityofphila water" in combined:
                            txn.qb_account = "Water"
                            txn.transaction_type = "Expense"
                        elif any(k in combined for k in ("gas", "pgw", "philadelphia gas")):
                            txn.qb_account = "Gas Expense"
                            txn.transaction_type = "Expense"
                        elif any(k in combined for k in ("peco", "electric")):
                            txn.qb_account = "PECO Expense"
                            txn.transaction_type = "Expense"
                        elif any(k in combined for k in ("mortgage", "loan payment", "principal")):
                            # Loans handled by loan_split pass; if it reaches here it's an
                            # unsplit loan payment — leave to manual review.
                            if not txn.qb_account:
                                txn.qb_account = "ASK"
                            if not txn.transaction_type:
                                txn.transaction_type = "Expense"
                        else:
                            # Default: subcontractor / R&M / construction work
                            if not txn.qb_account:
                                txn.qb_account = "Subcontractors Expense"
                            if not txn.transaction_type:
                                txn.transaction_type = "Expense"
                    txn.classified_by = (
                        f"property_sheet[{prop_name}] row {entry.row_num}: "
                        f"{entry.payee[:30]} {entry.description[:30]}"
                    )
                    classified.append(txn)
                    promoted += 1
                else:
                    # Multiple matches across different property sheets
                    props_str = ", ".join(set(p for p, _ in all_matches))
                    item.reason = (
                        f"{item.reason} | "
                        f"Property ambiguous: matches in {props_str}"
                    )
                    still_review_after_property.append(item)
                    ambiguous += 1

            review_items = still_review_after_property
            print()
            print(f"  Promoted to classified: {promoted}")
            print(f"  Ambiguous (multiple property matches): {ambiguous}")
            print(f"  No property match (unchanged): {unmatched}")
            print()
            print(f"Updated counts:")
            print(f"  Classified: {len(classified)}")
            print(f"  Review queue: {len(review_items)}")

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

    # =========================================================
    # 6.6.1 LOAN PAYMENTS SPLIT PASS (GJ Holdings)
    # =========================================================
    loan_ending_balances = {}
    if not args.no_loan_splits:
        loans_config = getattr(rules_module, "LOANS", None)
        if loans_config:
            print()
            print("=" * 90)
            print("LOAN PAYMENTS SPLIT PASS")
            print("=" * 90)
            try:
                from reconcile.loaders.loan_payments import load_all_loans
                from pathlib import Path as _Path
                loan_splits_by_loan = load_all_loans(loans_config, _Path(args.pcb_dir))
                from reconcile.loaders.loan_payments import get_loan_ending_balances
                loan_ending_balances = get_loan_ending_balances(loans_config, _Path(args.pcb_dir))
                splits_index = {}
                for loan_num, splits in loan_splits_by_loan.items():
                    for s in splits:
                        splits_index.setdefault((loan_num, s.txn_date), []).append(s)
            except Exception as e:
                print(f"  WARNING: Could not load loan splits: {e}")
                splits_index = {}

            from reconcile.engine import Transaction as _Transaction
            new_classified = []
            replaced_count = 0
            unmatched_loan_count = 0
            for txn in classified:
                if txn.qb_account == "SPLIT_LOAN":
                    loan_num = txn.qb_class
                    splits = splits_index.get((loan_num, txn.date), [])
                    if not splits:
                        from datetime import timedelta as _td
                        for delta in (-1, 1, -2, 2):
                            splits = splits_index.get((loan_num, txn.date + _td(days=delta)), [])
                            if splits:
                                break
                    # Conservation guard: splits must sum to the bank txn amount.
                    # Otherwise (e.g. a $38 loan fee sharing a date with a full
                    # payment) do NOT split — flag instead.
                    if splits:
                        split_total = float(sum(abs(s.amount) for s in splits))
                        if abs(split_total - abs(txn.amount)) > 1.00:
                            splits = []
                    if not splits:
                        txn.qb_account = "ASK"
                        txn.classified_by = f"LOAN_NO_MATCH[loan {loan_num} on {txn.date}]"
                        new_classified.append(txn)
                        unmatched_loan_count += 1
                        continue

                    loan_cfg = loans_config.get(loan_num, {})
                    is_stabilized = loan_cfg.get("is_stabilized", True)
                    property_class = loan_cfg.get("property", "")

                    for s in splits:
                        if s.component == "principal":
                            qb_acct = f"PCB Loan {loan_num}" if loan_cfg.get("servicer") == "PCB" else f"Fay Loan {loan_num}"
                            qb_class = property_class
                            ttype = "Liability"
                        elif s.component == "interest":
                            if is_stabilized:
                                qb_acct = "Interest Expense"
                                qb_class = property_class
                                ttype = "Expense"
                            else:
                                qb_acct = property_class
                                qb_class = ""
                                ttype = "Asset"
                        elif s.component == "escrow":
                            qb_acct = "Escrow"
                            qb_class = property_class
                            ttype = "Asset"
                        else:
                            qb_acct = "ASK"
                            qb_class = property_class
                            ttype = "Expense"

                        split_txn = _Transaction(
                            source_account=txn.source_account,
                            date=txn.date,
                            description=s.description,
                            amount=float(s.amount),
                            qb_account=qb_acct,
                            qb_class=qb_class,
                            transaction_type=ttype,
                            classified_by=f"loan_split[{loan_num} {s.component}]",
                        )
                        new_classified.append(split_txn)
                    replaced_count += 1
                else:
                    new_classified.append(txn)
            classified = new_classified

            print(f"  Loan payments replaced with splits: {replaced_count}")
            if unmatched_loan_count:
                print(f"  Loan payments with no CSV match (flagged ASK): {unmatched_loan_count}")
            print()
            print(f"Updated counts:")
            print(f"  Classified: {len(classified)}")

    # =========================================================
    # 6.6.2 WATER RANKING PASS (GJ Holdings)
    # =========================================================
    if not args.no_water_ranking:
        if any(t.qb_account == "WATER_RANKING" for t in classified):
            print()
            print("=" * 90)
            print("WATER RANKING PASS")
            print("=" * 90)
            from reconcile.water_ranking import assign_water_bills
            assigns, water_review_idx, audit = assign_water_bills(classified, rules_module=rules_module)
            for line in audit:
                print(f"  {line}")
            for a in assigns:
                t = classified[a.txn_index]
                t.qb_account = a.qb_account
                t.qb_class = a.qb_class
                t.transaction_type = a.transaction_type
                t.classified_by = a.classified_by
            from reconcile.engine import ReviewItem as _ReviewItem
            for idx in water_review_idx:
                t = classified[idx]
                review_items.append(_ReviewItem(
                    transaction=t,
                    reason=f"Water bill could not be assigned (rank/amount unclear)"
                ))
            classified = [t for i, t in enumerate(classified) if i not in set(water_review_idx)]

            print()
            print(f"Updated counts:")
            print(f"  Classified: {len(classified)}")
            print(f"  Review queue: {len(review_items)}")

    # =========================================================
    # 6.6.2b PECO RANKING PASS (Sophia Holdings)
    # =========================================================
    if not getattr(args, "no_peco_ranking", False):
        if any(t.qb_account == "PECO_RANKING" for t in classified):
            print()
            print("=" * 90)
            print("PECO RANKING PASS")
            print("=" * 90)
            from reconcile.peco_ranking import assign_peco_bills
            peco_assigns, peco_review_idx, peco_audit = assign_peco_bills(classified, rules_module=rules_module)
            for line in peco_audit:
                print(f"  {line}")
            for a in peco_assigns:
                t = classified[a.txn_index]
                t.qb_account = a.qb_account
                t.qb_class = a.qb_class
                t.transaction_type = a.transaction_type
                t.classified_by = a.classified_by
            from reconcile.engine import ReviewItem as _ReviewItem
            for idx in peco_review_idx:
                t = classified[idx]
                review_items.append(_ReviewItem(
                    transaction=t,
                    reason="PECO bill rank exceeded configured PECO_RANKING_ORDER"
                ))
            classified = [t for i, t in enumerate(classified) if i not in set(peco_review_idx)]
            print()
            print(f"Updated counts:")
            print(f"  Classified: {len(classified)}")
            print(f"  Review queue: {len(review_items)}")

    # =========================================================
    # 6.6.3 GAS / PECO 50/50 SPLIT PASS (GJ Holdings)
    # =========================================================
    if not args.no_gas_peco_split:
        split_props = getattr(rules_module, "GAS_PECO_SPLIT", None)
        if split_props and len(split_props) == 2:
            split_markers = {"GAS_SPLIT": "Phila Gas", "PECO_SPLIT": "PECO"}
            txns_to_split = [t for t in classified if t.qb_account in split_markers]
            if txns_to_split:
                print()
                print("=" * 90)
                print("GAS / PECO 50/50 SPLIT PASS")
                print("=" * 90)
                from reconcile.engine import Transaction as _Transaction
                new_classified = []
                replaced = 0
                for t in classified:
                    if t.qb_account in split_markers:
                        marker_label = split_markers[t.qb_account]
                        half = round(t.amount / 2.0, 2)
                        new_classified.append(_Transaction(
                            source_account=t.source_account,
                            date=t.date,
                            description=f"{marker_label} - {split_props[0]} (50%)",
                            amount=half,
                            qb_account=split_props[0],
                            qb_class="",
                            transaction_type="Asset",
                            classified_by=f"gas_peco_split[{marker_label} 50%]",
                        ))
                        new_classified.append(_Transaction(
                            source_account=t.source_account,
                            date=t.date,
                            description=f"{marker_label} - {split_props[1]} (50%)",
                            amount=round(t.amount - half, 2),
                            qb_account=split_props[1],
                            qb_class="",
                            transaction_type="Asset",
                            classified_by=f"gas_peco_split[{marker_label} 50%]",
                        ))
                        replaced += 1
                    else:
                        new_classified.append(t)
                classified = new_classified
                print(f"  Replaced {replaced} bills with 50/50 splits across {split_props[0]} + {split_props[1]}")
                print()
                print(f"Updated counts:")
                print(f"  Classified: {len(classified)}")

    # =========================================================
    # 6.6.4 RENTREDI SPLIT PASS (GJ Holdings)
    # =========================================================
    if not args.no_rentredi:
        rentredi_suffix = rules_module.ENTITY.get("rentredi_bank_suffix")
        if rentredi_suffix:
            rentredi_txns = [t for t in classified if t.qb_account == "RENTREDI_SPLIT"]
            if rentredi_txns:
                print()
                print("=" * 90)
                print("RENTREDI SPLIT PASS")
                print("=" * 90)
                from pathlib import Path as _Path
                rentredi_path = _Path(args.pcb_dir).parent / "Rent Redi Deposits Jan-march.csv"
                if not rentredi_path.exists():
                    print(f"  WARNING: RentRedi CSV not found at {rentredi_path}")
                else:
                    from reconcile.loaders.rent_redi import load_rentredi_deposits, find_deposit_for_bank_txn
                    from reconcile.engine import Transaction as _Transaction
                    from decimal import Decimal as _Decimal
                    deposits = load_rentredi_deposits(rentredi_path, bank_suffix=rentredi_suffix)
                    print(f"  Loaded {len(deposits)} deposits for bank suffix xxxx{rentredi_suffix}")

                    new_classified = []
                    replaced = 0
                    unmatched = 0
                    for t in classified:
                        if t.qb_account == "RENTREDI_SPLIT":
                            d = find_deposit_for_bank_txn(deposits, t.date, _Decimal(str(t.amount)))
                            if not d:
                                _nr_default = getattr(rules_module, "RENTREDI_NO_MATCH_DEFAULT", None)
                                if _nr_default:
                                    t.qb_account = _nr_default[0]
                                    t.qb_class = _nr_default[1]
                                    t.transaction_type = "Income"
                                    t.classified_by = f"RENTREDI_NO_MATCH_DEFAULT[{_nr_default[1]}]"
                                else:
                                    t.qb_account = "ASK"
                                    t.classified_by = f"RENTREDI_NO_MATCH"
                                new_classified.append(t)
                                unmatched += 1
                                continue
                            for r in d.rents:
                                rent_txn = _Transaction(
                                    source_account=t.source_account,
                                    date=t.date,
                                    description=f"Rent - {r.property} {r.unit} - {r.tenant}",
                                    amount=float(r.amount),
                                    qb_account="Rental Income",
                                    qb_class=r.property,
                                    transaction_type="Income",
                                    classified_by=f"rentredi_split[{r.property} {r.unit} - {r.description}]",
                                )
                                new_classified.append(rent_txn)
                            replaced += 1
                        else:
                            new_classified.append(t)
                    classified = new_classified
                    print(f"  Replaced {replaced} RentRedi deposits with per-unit rent splits")
                    if unmatched:
                        print(f"  Unmatched RentRedi deposits (flagged ASK): {unmatched}")
                    print()
                    print(f"Updated counts:")
                    print(f"  Classified: {len(classified)}")

    # =========================================================
    # 6.6.5 EQUITY CLUSTER PASS (capital contributions / distributions)
    # =========================================================
    # Detects groups of equal-amount transactions within a 14-day window.
    # When cluster size matches the number of members, assigns each to
    # a member in fixed order (Steve, Josh, Gene, Boris).
    if not getattr(args, "no_equity_clusters", False):
        members = rules_module.ENTITY.get("members", [])
        equity_accounts = rules_module.ENTITY.get("equity_accounts", {})
        if members and equity_accounts:
            print()
            print("=" * 90)
            print("EQUITY CLUSTER PASS")
            print("=" * 90)
            from reconcile.equity_pass import assign_equity_clusters
            
            # Run equity assignment on review_items (these are unmatched candidates)
            review_txns = [item.transaction for item in review_items]
            assignments, audit = assign_equity_clusters(review_txns, members, equity_accounts)
            for line in audit:
                print(f"  {line}")
            
            if assignments:
                # Apply assignments and promote those review items to classified
                assigned_indices = set()
                for a in assignments:
                    txn = review_txns[a.txn_index]
                    txn.qb_account = a.qb_account
                    txn.qb_class = a.qb_class
                    txn.transaction_type = a.transaction_type
                    txn.classified_by = a.classified_by
                    classified.append(txn)
                    assigned_indices.add(a.txn_index)
                
                # Remove assigned items from review_items
                review_items = [
                    item for i, item in enumerate(review_items)
                    if i not in assigned_indices
                ]
                
                print()
                print(f"Updated counts:")
                print(f"  Classified: {len(classified)}")
                print(f"  Review queue: {len(review_items)}")

    # =========================================================
    # 6.6.6 STORMWATER ROUTING PASS (10th Fairmount)
    # =========================================================
    # Routes STORMWATER_TD-marked transactions to properties using an ordered
    # routing table from the rules module. Activates only if (a) the rules
    # module defines STORMWATER_ROUTING_TD, and (b) at least one classified
    # transaction has qb_account == "STORMWATER_TD".
    stormwater_routing = getattr(rules_module, "STORMWATER_ROUTING_TD", None)
    if stormwater_routing and any(t.qb_account == "STORMWATER_TD" for t in classified):
        print()
        print("=" * 90)
        print("STORMWATER ROUTING PASS")
        print("=" * 90)
        from reconcile.loaders.stormwater import assign_stormwater_bills
        sw_assignments, sw_review_idx, sw_audit = assign_stormwater_bills(
            classified, stormwater_routing
        )
        for line in sw_audit:
            print(line)

        # Apply assignments
        for a in sw_assignments:
            t = classified[a.txn_index]
            t.qb_account = a.qb_account
            t.qb_class = a.qb_class
            t.transaction_type = a.transaction_type
            t.classified_by = a.classified_by
            if a.description_suffix and a.description_suffix not in t.description:
                t.description = f"{t.description} — {a.description_suffix}"

        # Move ungrouped (size-mismatch) stormwater items to review queue
        from reconcile.engine import ReviewItem as _ReviewItem
        for idx in sw_review_idx:
            t = classified[idx]
            review_items.append(_ReviewItem(
                transaction=t,
                reason="Stormwater group size doesn't match routing table; route manually."
            ))
        classified = [t for i, t in enumerate(classified) if i not in set(sw_review_idx)]

        print()
        print(f"  Routed: {len(sw_assignments)}")
        print(f"  Sent to review: {len(sw_review_idx)}")
        print(f"Updated counts:")
        print(f"  Classified: {len(classified)}")
        print(f"  Review queue: {len(review_items)}")

    # Snapshot classified transactions BEFORE distribution passes wipe out
    # individual items. The vendor tracker needs to see real vendor names
    # (ANGEL HEATING, etc.) before they're aggregated into PROPORTIONAL_DISTRIBUTION.
    pre_distribution_snapshot = list(classified)

    # 6.55 One-shot dump: move all review items into PROPORTIONAL bucket
    if args.distribute_all_review_items and review_items:
        print()
        print("=" * 90)
        print("DISTRIBUTE ALL REVIEW ITEMS (one-shot)")
        print("=" * 90)
        print(f"  Moving {len(review_items)} review queue items into PROPORTIONAL_DISTRIBUTION pool")
        print(f"  Total: ${sum(r.transaction.amount for r in review_items):,.2f}")
        for item in review_items:
            txn = item.transaction
            txn.qb_account = "Construction Costs"
            txn.qb_class = "PROPORTIONAL_DISTRIBUTION"
            txn.transaction_type = "Expense"
            txn.classified_by = "distribute_all_review_items[one-shot]"
            classified.append(txn)
        review_items = []
        print(f"  Review queue cleared")

    # 6.6 Post-process: distribute PROPORTIONAL_DISTRIBUTION items across
    # properties using Chase ratios from rules module
    if not args.no_proportional_distribution:
        ratios = getattr(rules_module, "CHASE_PROPERTY_RATIOS", None)
        if ratios:
            print()
            print("=" * 90)
            print("PROPORTIONAL DISTRIBUTION PASS")
            print("=" * 90)

            # Find all txns with PROPORTIONAL_DISTRIBUTION class
            prop_txns = [t for t in classified
                         if t.qb_class == "PROPORTIONAL_DISTRIBUTION"]

            if not prop_txns:
                print("  No PROPORTIONAL_DISTRIBUTION items to distribute")
            else:
                # Sum and remove from classified
                total_amount = sum(t.amount for t in prop_txns)
                print(f"  Found {len(prop_txns)} PROPORTIONAL items totaling ${total_amount:.2f}")

                classified = [t for t in classified
                              if t.qb_class != "PROPORTIONAL_DISTRIBUTION"]

                # Create 6 distribution transactions
                from datetime import date as date_cls
                from reconcile.engine import Transaction

                # Use the latest txn date as the distribution date
                last_date = max((t.date for t in prop_txns), default=date_cls.today())

                # Compute amounts for each property; track running sum to handle rounding
                amounts = {}
                running = 0.0
                props = list(ratios.items())
                for prop, ratio in props[:-1]:
                    amt = round(total_amount * ratio, 2)
                    amounts[prop] = amt
                    running += amt
                # Last property absorbs rounding adjustment
                last_prop, _ = props[-1]
                amounts[last_prop] = round(total_amount - running, 2)

                # Create distribution transactions
                for prop, amt in amounts.items():
                    if abs(amt) < 0.01:
                        continue
                    dist_txn = Transaction(
                        source_account="DISTRIBUTION",
                        date=last_date,
                        description=f"Proportional distribution of unmatched Chase items ({len(prop_txns)} txns) to {prop}",
                        amount=amt,
                        qb_account="Construction Costs",
                        qb_class=prop,
                        transaction_type="Expense",
                        classified_by=f"proportional_distribution[{ratios[prop]*100:.2f}% of ${total_amount:.2f}]",
                    )
                    classified.append(dist_txn)
                    print(f"  {prop:<25} ${amt:>10.2f} ({ratios[prop]*100:.2f}%)")

                print()
                print(f"Updated counts:")
                print(f"  Classified: {len(classified)}")
                print(f"  Review queue: {len(review_items)}")
        else:
            print()
            print("(No CHASE_PROPERTY_RATIOS in rules module; skipping proportional distribution)")

    # 6.7 Post-process: distribute AMEX charges across properties using Chase ratios
    # Used when AMEX statements are not available (e.g., card cancelled).
    if args.distribute_amex:
        ratios = getattr(rules_module, "CHASE_PROPERTY_RATIOS", None)
        if ratios:
            print()
            print("=" * 90)
            print("AMEX DISTRIBUTION PASS")
            print("=" * 90)

            amex_txns = [t for t in classified if t.qb_account == "AMEX"]

            if not amex_txns:
                print("  No AMEX transactions to distribute")
            else:
                total_amount = sum(t.amount for t in amex_txns)
                print(f"  Found {len(amex_txns)} AMEX autopay txns totaling ${total_amount:.2f}")

                classified = [t for t in classified if t.qb_account != "AMEX"]

                from datetime import date as date_cls
                from reconcile.engine import Transaction

                last_date = max((t.date for t in amex_txns), default=date_cls.today())

                amounts = {}
                running = 0.0
                props = list(ratios.items())
                for prop, ratio in props[:-1]:
                    amt = round(total_amount * ratio, 2)
                    amounts[prop] = amt
                    running += amt
                last_prop, _ = props[-1]
                amounts[last_prop] = round(total_amount - running, 2)

                for prop, amt in amounts.items():
                    if abs(amt) < 0.01:
                        continue
                    dist_txn = Transaction(
                        source_account="DISTRIBUTION",
                        date=last_date,
                        description=f"AMEX charges distributed to {prop} (no AMEX statements available; card cancelled)",
                        amount=amt,
                        qb_account="Construction Costs",
                        qb_class=prop,
                        transaction_type="Expense",
                        classified_by=f"amex_distribution[{ratios[prop]*100:.2f}% of ${total_amount:.2f}]",
                    )
                    classified.append(dist_txn)
                    print(f"  {prop:<25} ${amt:>10.2f} ({ratios[prop]*100:.2f}%)")

                print()
                print(f"Updated counts:")
                print(f"  Classified: {len(classified)}")
                print(f"  Review queue: {len(review_items)}")
        else:
            print()
            print("(No CHASE_PROPERTY_RATIOS in rules module; skipping AMEX distribution)")

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
        loan_ending_balances=loan_ending_balances,
        output_dir=args.output_dir,
        checks_csv=None,
        vendor_tracker_transactions=pre_distribution_snapshot,
        retail_patterns=getattr(rules_module, "RETAIL_VENDOR_PATTERNS", []),
    )
    for label, path in paths.items():
        print(f"  {label}: {path}")


if __name__ == "__main__":
    main()
