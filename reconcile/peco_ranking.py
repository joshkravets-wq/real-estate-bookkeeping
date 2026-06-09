"""
PECO Ranking Pass — entity-agnostic.

Variable bills ranked per month. Highest amount in month → first property in
PECO_RANKING_ORDER, 2nd highest → second property, etc.

Activation: rules module must define PECO_RANKING_ORDER. Bank rule must classify
PECO bills with qb_account == "PECO_RANKING".

PECO_RANKING_ORDER schema: list of (qb_account, qb_class, type, label) tuples.
Order matters — index 0 = highest, index 1 = 2nd highest, etc. Bills beyond
the configured ranks go to review.
"""

from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from typing import List


@dataclass
class PecoAssignment:
    txn_index: int
    qb_account: str
    qb_class: str
    transaction_type: str
    classified_by: str


def assign_peco_bills(transactions: list, rules_module=None) -> tuple:
    """
    Find PECO transactions, rank per month, assign by PECO_RANKING_ORDER.

    Args:
        transactions: list of Transaction objects from engine output.
        rules_module: entity's rules module; must define PECO_RANKING_ORDER.

    Returns:
        (assignments, review_indices, audit_lines)
    """
    audit: List[str] = []
    assignments: List[PecoAssignment] = []
    review_indices: List[int] = []

    rank_order = getattr(rules_module, "PECO_RANKING_ORDER", None)
    if not rank_order:
        return assignments, review_indices, audit

    # Find PECO transactions (marker_account OR description-based)
    peco_indices = []
    for i, t in enumerate(transactions):
        if getattr(t, "qb_account", None) == "PECO_RANKING":
            peco_indices.append(i)

    if not peco_indices:
        return assignments, review_indices, audit

    audit.append(f"Found {len(peco_indices)} PECO transactions.")

    # Group by month
    by_month = defaultdict(list)
    for i in peco_indices:
        t = transactions[i]
        key = (t.date.year, t.date.month)
        by_month[key].append(i)

    # For each month, rank by abs(amount) descending and assign
    for month_key in sorted(by_month.keys()):
        indices = by_month[month_key]
        indices_ranked = sorted(
            indices,
            key=lambda i: abs(transactions[i].amount),
            reverse=True,
        )
        for rank, idx in enumerate(indices_ranked):
            if rank < len(rank_order):
                qb_acct, qb_class, ttype, label = rank_order[rank]
                rank_str = "highest" if rank == 0 else f"rank-{rank+1}"
                assignments.append(PecoAssignment(
                    txn_index=idx,
                    qb_account=qb_acct,
                    qb_class=qb_class,
                    transaction_type=ttype,
                    classified_by=f"peco_rank[{month_key[0]}-{month_key[1]:02d} {rank_str} -> {label}]",
                ))
            else:
                review_indices.append(idx)
                audit.append(
                    f"  MONTH {month_key}: rank {rank+1} ${abs(transactions[idx].amount):.2f} "
                    f"-> review (no slot in PECO_RANKING_ORDER)"
                )

    audit.append(f"Total assigned: {len(assignments)}; flagged for review: {len(review_indices)}")
    return assignments, review_indices, audit
