"""
Water Ranking Pass for GJ Holdings

Two-stage classification:

STAGE 1 - Fixed-amount rules (rules engine could handle but we keep them here
for cohesion with stage 2):
  - $21.64 -> 2415 N 4th St + 2431 N 3rd St (Asset, chronologically alternating)
  - $33.25 -> 314 W Norris St (Expense - sprinkler line)
  - $35.05 -> 5461 W Berks St (Asset - pre-stab capitalized)
  - $49.23 -> 314 W Norris St (Expense - other unit)
  - $81.49 -> 1948 N Orianna St (Expense - recurring)

STAGE 2 - Variable bills (everything not matching stage 1) ranked per month:
  - 1st highest variable -> 314 W Norris St (Expense - regular water)
  - 2nd highest variable -> 507 W Dauphin St (Expense)
  - 3rd highest variable, ONLY IF no $81.49 matched in same month -> 1948 N Orianna St
  - Anything beyond 3rd, or 3rd when $81.49 already present -> review queue
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date


@dataclass
class WaterAssignment:
    txn_index: int
    qb_account: str
    qb_class: str
    transaction_type: str
    classified_by: str


# Fixed-amount mapping (amount -> (qb_account, qb_class, type, label))
# For pre-stab properties: qb_account = property address, no class.
# For stabilized properties: qb_account = "Water Expense", class = property address.
FIXED_AMOUNT_RULES = {
    33.25: ("Water Expense", "314 W Norris St", "Expense", "sprinkler line"),
    35.05: ("5461 W Berks St", "", "Asset", "5461 W Berks recurring (pre-stab)"),
    49.23: ("Water Expense", "314 W Norris St", "Expense", "other unit"),
    81.49: ("Water Expense", "1948 N Orianna St", "Expense", "Orianna recurring"),
}
LOT_AMOUNT = 21.64
LOT_PROPERTIES = ["2415 N 4th St", "2431 N 3rd St"]  # chronological alternating

# Variable-rank mapping: rank within month (after fixed) -> property
# Rank 0 = highest, 1 = 2nd, 2 = 3rd
VARIABLE_RANK_PROPERTIES = [
    ("Water Expense", "314 W Norris St", "Expense", "regular water"),
    ("Water Expense", "507 W Dauphin St", "Expense", "regular water"),
    # Rank 2 (3rd highest) handled specially - only if no $81.49 in month
]

# Tolerance for matching amounts to fixed values
AMOUNT_TOLERANCE = 0.05


def _amount_matches(actual: float, target: float, tolerance: float = AMOUNT_TOLERANCE) -> bool:
    return abs(abs(actual) - target) <= tolerance


def assign_water_bills(transactions: list) -> tuple:
    """
    Find water transactions in `transactions`, apply fixed-amount + ranking rules.
    
    Args:
      transactions: list of Transaction objects
    
    Returns:
      (assignments: list of WaterAssignment,
       review_indices: list of txn indices flagged for review,
       audit_log: list of strings)
    """
    audit = []

    # Step 1: Find water transactions
    water_indices = []
    for i, t in enumerate(transactions):
        is_water = False
        if getattr(t, "qb_account", None) == "WATER_RANKING":
            is_water = True
        elif "CITYOFPHILA" in (t.description or ""):
            is_water = True
        if is_water:
            water_indices.append(i)

    if not water_indices:
        audit.append("No water transactions found.")
        return [], [], audit

    audit.append(f"Found {len(water_indices)} water transactions.")

    assignments = []
    review_indices = []

    # Step 2: Apply fixed-amount rules
    handled = set()
    fixed_amount_present_per_month = defaultdict(set)  # month_key -> set of fixed amounts seen
    lot_chrono_per_month = defaultdict(list)  # month_key -> list of indices for lot bills (preserve order)

    for i in water_indices:
        t = transactions[i]
        amt = abs(t.amount)
        month_key = (t.date.year, t.date.month)

        # Lot bill?
        if _amount_matches(amt, LOT_AMOUNT):
            lot_chrono_per_month[month_key].append(i)
            handled.add(i)
            continue

        # Other fixed amounts?
        matched = False
        for fixed_amt, (qb_acct, qb_class, ttype, label) in FIXED_AMOUNT_RULES.items():
            if _amount_matches(amt, fixed_amt):
                assignments.append(WaterAssignment(
                    txn_index=i,
                    qb_account=qb_acct,
                    qb_class=qb_class,
                    transaction_type=ttype,
                    classified_by=f"water_fixed[${fixed_amt:.2f} = {label}]",
                ))
                fixed_amount_present_per_month[month_key].add(fixed_amt)
                handled.add(i)
                matched = True
                break
        if matched:
            continue
        # Otherwise, leave unhandled for ranking pass

    # Step 3: Assign lots chronologically per month
    for month_key, lot_indices in lot_chrono_per_month.items():
        # Sort by date ascending (already chronological since transactions are date-ordered, but be safe)
        lot_indices_sorted = sorted(lot_indices, key=lambda i: transactions[i].date)
        for j, idx in enumerate(lot_indices_sorted):
            if j < len(LOT_PROPERTIES):
                prop = LOT_PROPERTIES[j]
                assignments.append(WaterAssignment(
                    txn_index=idx,
                    qb_account=prop,
                    qb_class="",
                    transaction_type="Asset",
                    classified_by=f"water_lot[${LOT_AMOUNT:.2f} chrono {j+1} - {prop}]",
                ))
            else:
                review_indices.append(idx)
                audit.append(f"  MONTH {month_key}: extra lot bill #{j+1} flagged for review")

    # Step 4: Variable-rank pass - collect unhandled water bills per month
    unhandled_per_month = defaultdict(list)
    for i in water_indices:
        if i in handled:
            continue
        t = transactions[i]
        month_key = (t.date.year, t.date.month)
        unhandled_per_month[month_key].append(i)

    for month_key, indices in unhandled_per_month.items():
        # Sort by amount descending
        indices_ranked = sorted(
            indices,
            key=lambda i: abs(transactions[i].amount),
            reverse=True,
        )

        has_orianna_recurring = 81.49 in fixed_amount_present_per_month[month_key]

        for rank, idx in enumerate(indices_ranked):
            if rank == 0:
                # Highest -> Norris regular
                qb_acct, qb_class, ttype, label = VARIABLE_RANK_PROPERTIES[0]
                assignments.append(WaterAssignment(
                    txn_index=idx,
                    qb_account=qb_acct,
                    qb_class=qb_class,
                    transaction_type=ttype,
                    classified_by=f"water_rank[month {month_key[0]}-{month_key[1]:02d} highest -> Norris {label}]",
                ))
            elif rank == 1:
                # 2nd highest -> Dauphin
                qb_acct, qb_class, ttype, label = VARIABLE_RANK_PROPERTIES[1]
                assignments.append(WaterAssignment(
                    txn_index=idx,
                    qb_account=qb_acct,
                    qb_class=qb_class,
                    transaction_type=ttype,
                    classified_by=f"water_rank[month {month_key[0]}-{month_key[1]:02d} 2nd -> Dauphin {label}]",
                ))
            elif rank == 2 and not has_orianna_recurring:
                # 3rd highest -> Orianna fallback (only if no $81.49 this month)
                assignments.append(WaterAssignment(
                    txn_index=idx,
                    qb_account="Water Expense",
                    qb_class="1948 N Orianna St",
                    transaction_type="Expense",
                    classified_by=f"water_rank[month {month_key[0]}-{month_key[1]:02d} 3rd -> Orianna fallback (no $81.49 this month)]",
                ))
            else:
                # Either rank 3+ or rank 2 with $81.49 already present -> review
                review_indices.append(idx)
                reason = "no slot in variable ranking"
                if rank == 2 and has_orianna_recurring:
                    reason = "3rd-rank skipped because $81.49 (Orianna recurring) already in month"
                audit.append(f"  MONTH {month_key}: variable rank {rank+1} ${abs(transactions[idx].amount):.2f} -> review ({reason})")

    audit.append(f"Total assigned: {len(assignments)}; flagged for review: {len(review_indices)}")
    return assignments, review_indices, audit


# -------------------- CLI test against actual Q1 2026 data --------------------

if __name__ == "__main__":
    from datetime import date as dt_date
    from dataclasses import dataclass as dc

    @dc
    class MockTxn:
        date: dt_date
        amount: float
        description: str
        qb_account: str = "WATER_RANKING"

    # All Q1 2026 GJ Holdings water bills from bank CSV
    txns = [
        MockTxn(dt_date(2026, 1, 21), -35.05, "External Withdrawal CITYOFPHILA"),
        MockTxn(dt_date(2026, 1, 27), -33.25, "External Withdrawal CITYOFPHILA"),
        MockTxn(dt_date(2026, 1, 30), -81.49, "External Withdrawal CITYOFPHILA"),
        MockTxn(dt_date(2026, 2, 2), -21.64, "External Withdrawal CITYOFPHILA"),
        MockTxn(dt_date(2026, 2, 2), -21.64, "External Withdrawal CITYOFPHILA"),
        MockTxn(dt_date(2026, 2, 2), -61.87, "External Withdrawal CITYOFPHILA"),
        MockTxn(dt_date(2026, 2, 2), -72.98, "External Withdrawal CITYOFPHILA"),
        MockTxn(dt_date(2026, 2, 2), -100.00, "External Withdrawal CITYOFPHILA"),
        MockTxn(dt_date(2026, 2, 24), -35.05, "External Withdrawal CITYOFPHILA"),
        MockTxn(dt_date(2026, 2, 26), -33.25, "External Withdrawal CITYOFPHILA"),
        MockTxn(dt_date(2026, 3, 2), -81.49, "External Withdrawal CITYOFPHILA"),
        MockTxn(dt_date(2026, 3, 3), -21.64, "External Withdrawal CITYOFPHILA"),
        MockTxn(dt_date(2026, 3, 3), -21.64, "External Withdrawal CITYOFPHILA"),
        MockTxn(dt_date(2026, 3, 3), -49.23, "External Withdrawal CITYOFPHILA"),
        MockTxn(dt_date(2026, 3, 3), -93.46, "External Withdrawal CITYOFPHILA"),
        MockTxn(dt_date(2026, 3, 3), -98.27, "External Withdrawal CITYOFPHILA"),
        MockTxn(dt_date(2026, 3, 25), -35.05, "External Withdrawal CITYOFPHILA"),
        MockTxn(dt_date(2026, 3, 26), -33.25, "External Withdrawal CITYOFPHILA"),
        MockTxn(dt_date(2026, 3, 31), -81.49, "External Withdrawal CITYOFPHILA"),
    ]

    assigns, reviews, audit = assign_water_bills(txns)

    print("AUDIT:")
    for line in audit:
        print(f"  {line}")
    print()

    print(f"ASSIGNMENTS ({len(assigns)}):")
    for a in assigns:
        t = txns[a.txn_index]
        print(f"  {t.date} ${abs(t.amount):>7,.2f}  qb={a.qb_account:25s} class={a.qb_class:25s} type={a.transaction_type:8s}")
        print(f"      [{a.classified_by}]")

    if reviews:
        print()
        print(f"REVIEW QUEUE ({len(reviews)}):")
        for i in reviews:
            t = txns[i]
            print(f"  {t.date} ${abs(t.amount):>7,.2f}  {t.description[:40]}")
