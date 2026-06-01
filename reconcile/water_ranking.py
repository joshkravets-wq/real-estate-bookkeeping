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


def assign_water_bills(transactions: list, rules_module=None) -> tuple:
    """
    Find water transactions in `transactions`, apply fixed-amount + ranking rules.

    Args:
      transactions: list of Transaction objects
      rules_module: optional rules module. If provided, reads:
        - WATER_FIXED_RULES (dict: amount -> (qb_account, qb_class, type, label))
        - WATER_LOT_CONFIG (dict: {"amount": float, "properties": [str, ...]})
        - WATER_VARIABLE_RANK (list of (qb_account, qb_class, type, label))
        - WATER_RANK_FALLBACK_SKIP_IF_AMOUNT (float or None): if a fixed-amount
          matching this value appears in a month, skip rank-3 fallback.
        - WATER_RANK_FALLBACK (tuple): (qb_account, qb_class, type, label) for rank-3
          fallback property (only used if WATER_RANK_FALLBACK_SKIP_IF_AMOUNT not seen).
      If rules_module is None or doesn't define these, falls back to GJ Holdings
      hardcoded defaults (preserves backward compat).

    Returns:
      (assignments: list of WaterAssignment,
       review_indices: list of txn indices flagged for review,
       audit_log: list of strings)
    """
    # Read config from rules module, with GJ Holdings defaults
    fixed_rules = getattr(rules_module, "WATER_FIXED_RULES", None) or FIXED_AMOUNT_RULES
    lot_cfg_raw = getattr(rules_module, "WATER_LOT_CONFIG", None) or {
        "amount": LOT_AMOUNT, "properties": LOT_PROPERTIES,
    }
    # Normalize: WATER_LOT_CONFIG can be a single dict OR a list of dicts.
    # Each entry: {"amount": float, "properties": [str, ...], "type": "Asset"|"Expense" (optional)}
    if isinstance(lot_cfg_raw, dict):
        lot_configs = [lot_cfg_raw]
    else:
        lot_configs = list(lot_cfg_raw)

    variable_rank = getattr(rules_module, "WATER_VARIABLE_RANK", None) or VARIABLE_RANK_PROPERTIES
    fallback_skip_amt = getattr(rules_module, "WATER_RANK_FALLBACK_SKIP_IF_AMOUNT", 81.49)
    fallback_props = getattr(rules_module, "WATER_RANK_FALLBACK", None) or (
        "Water Expense", "1948 N Orianna St", "Expense", "Orianna fallback",
    )

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
    # Lot bills queued per (month, lot_config_idx) so multiple lot groups can coexist
    lot_chrono_per_month = defaultdict(list)  # (month_key, lot_cfg_idx) -> list of indices

    for i in water_indices:
        t = transactions[i]
        amt = abs(t.amount)
        month_key = (t.date.year, t.date.month)

        # Lot bill? Try each configured lot group.
        lot_matched = False
        for lot_idx, lot_entry in enumerate(lot_configs):
            if _amount_matches(amt, lot_entry["amount"]):
                lot_chrono_per_month[(month_key, lot_idx)].append(i)
                handled.add(i)
                lot_matched = True
                break
        if lot_matched:
            continue

        # Other fixed amounts?
        matched = False
        for fixed_amt, (qb_acct, qb_class, ttype, label) in fixed_rules.items():
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

    # Step 3: Assign lots chronologically per month, per lot config group
    for (month_key, lot_idx), lot_indices in lot_chrono_per_month.items():
        lot_entry = lot_configs[lot_idx]
        lot_amount_value = lot_entry["amount"]
        lot_properties_value = lot_entry["properties"]
        lot_type = lot_entry.get("type", "Asset")
        # Stabilized: qb_account = "Water Expense", class = property
        # Pre-stab (default): qb_account = property name, no class
        # Sort by date ascending
        lot_indices_sorted = sorted(lot_indices, key=lambda i: transactions[i].date)
        for j, idx in enumerate(lot_indices_sorted):
            if j < len(lot_properties_value):
                prop = lot_properties_value[j]
                if lot_type == "Expense":
                    qb_acct = "Water Expense"
                    qb_class = prop
                else:
                    qb_acct = prop
                    qb_class = ""
                assignments.append(WaterAssignment(
                    txn_index=idx,
                    qb_account=qb_acct,
                    qb_class=qb_class,
                    transaction_type=lot_type,
                    classified_by=f"water_lot[${lot_amount_value:.2f} chrono {j+1} - {prop}]",
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

        has_fallback_skip_amount = fallback_skip_amt is not None and fallback_skip_amt in fixed_amount_present_per_month[month_key]

        # GJ Holdings backward-compat: if variable_rank has only 2 entries but
        # fallback_props is provided, append fallback as rank-3 (subject to skip-amount logic).
        effective_ranks = list(variable_rank)
        rank3_is_fallback = False
        if len(effective_ranks) == 2 and fallback_props:
            effective_ranks.append(fallback_props)
            rank3_is_fallback = True

        for rank, idx in enumerate(indices_ranked):
            # Skip rank 3 (effective_ranks[2]) if fallback-skip amount seen this month
            # AND rank-3 is the dynamically-added fallback (GJ Holdings semantics).
            if rank == 2 and rank3_is_fallback and has_fallback_skip_amount:
                review_indices.append(idx)
                audit.append(f"  MONTH {month_key}: rank-3 ${abs(transactions[idx].amount):.2f} -> review (fallback skipped because ${fallback_skip_amt:.2f} present)")
                continue

            if rank < len(effective_ranks):
                qb_acct, qb_class, ttype, label = effective_ranks[rank]
                rank_label = "highest" if rank == 0 else f"rank-{rank+1}"
                assignments.append(WaterAssignment(
                    txn_index=idx,
                    qb_account=qb_acct,
                    qb_class=qb_class,
                    transaction_type=ttype,
                    classified_by=f"water_rank[month {month_key[0]}-{month_key[1]:02d} {rank_label} -> {label}]",
                ))
            else:
                # Beyond configured ranks -> review
                review_indices.append(idx)
                reason = "no slot in variable ranking"
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
