"""
Adds GJ Holdings integration to run_reconcile.py.

Run once at start of next session, then test with:
  python3 -m reconcile.run_reconcile \
    --entity gj_holdings \
    --period "Jan-Mar 2026" \
    --pcb-dir "/Users/Josh/Documents/Letters to be printed/Properties/Standard Bus. Docs/Bookkeeping/Bank Accounts/GJ Holdings" \
    --no-proportional-distribution \
    --output-dir ./output

Adds:
  - 4 CLI flags: --no-loan-splits, --no-water-ranking, --no-gas-peco-split, --no-rentredi
  - Loan payments split pass (replaces SPLIT_LOAN markers with prin/int/escrow rows)
  - Water ranking pass (uses reconcile/water_ranking.py)
  - Gas/PECO 50/50 split pass (replaces single bill with 2 rows)
  - RentRedi split pass (replaces single deposit with N per-unit rent rows)
"""

from pathlib import Path

p = Path.home() / "real-estate-bookkeeping" / "reconcile" / "run_reconcile.py"
src = p.read_text()
changes = 0

# Patch 1: Add 4 new CLI flags
old_flag_anchor = '''    parser.add_argument(
        "--distribute-amex",'''

new_flag_addition = '''    parser.add_argument(
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
        "--distribute-amex",'''

if "--no-loan-splits" in src:
    print("Patch 1: flags already added", flush=True)
elif old_flag_anchor in src:
    src = src.replace(old_flag_anchor, new_flag_addition)
    changes += 1
    print("Patch 1: 4 new CLI flags added", flush=True)
else:
    print("Patch 1: ANCHOR NOT FOUND", flush=True)

# Patch 2: Add 4 new passes before pre_distribution_snapshot
old_anchor = '''    # Snapshot classified transactions BEFORE distribution passes wipe out
    # individual items. The vendor tracker needs to see real vendor names
    # (ANGEL HEATING, etc.) before they're aggregated into PROPORTIONAL_DISTRIBUTION.
    pre_distribution_snapshot = list(classified)'''

new_block = '''    # =========================================================
    # 6.6.1 LOAN PAYMENTS SPLIT PASS (GJ Holdings)
    # =========================================================
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
            assigns, water_review_idx, audit = assign_water_bills(classified)
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

    # Snapshot classified transactions BEFORE distribution passes wipe out
    # individual items. The vendor tracker needs to see real vendor names
    # (ANGEL HEATING, etc.) before they're aggregated into PROPORTIONAL_DISTRIBUTION.
    pre_distribution_snapshot = list(classified)'''

if "LOAN PAYMENTS SPLIT PASS" in src:
    print("Patch 2: passes already added", flush=True)
elif old_anchor in src:
    src = src.replace(old_anchor, new_block)
    changes += 1
    print("Patch 2: 4 new GJ Holdings passes inserted", flush=True)
else:
    print("Patch 2: ANCHOR NOT FOUND", flush=True)

p.write_text(src)
print(f"\n{changes}/2 patches applied")
