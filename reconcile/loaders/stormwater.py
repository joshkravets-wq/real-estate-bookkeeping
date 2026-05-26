"""
Stormwater bill routing pass.

For entities with multiple properties whose stormwater bills hit one bank
account as a daily batch (e.g., 10th Fairmount TD account receives 3 × $21.64
each month for 1012 Fairmount, 1008R Fairmount, and 1008 Fairmount which is
intercompany-Veit), this pass routes each bill to a property using a fixed
ordered routing table from the rules module.

Activation: rules module must define STORMWATER_ROUTING_TD (or analogous list).
Bank rule must classify the bills with qb_account == "STORMWATER_TD".

The pass groups STORMWATER_TD-tagged txns by date, then assigns each day's
group to the routing table entries in order.

Routing entry shape:
    {
        "amount": 21.64,
        "account": "1012 FAIRMOUNT AVENUE",  # QB Account
        "type": "Asset",                     # transaction_type
        "class": None,                       # QB Class (None = no class)
        "notes": "...",                      # optional, prepended to description
    }
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import List


@dataclass
class StormwaterAssignment:
    txn_index: int
    qb_account: str
    qb_class: str
    transaction_type: str
    classified_by: str
    description_suffix: str


def assign_stormwater_bills(
    classified: list,
    routing_table: list,
    marker_account: str = "STORMWATER_TD",
):
    """Assign STORMWATER_TD-marked transactions to properties via routing_table.

    Args:
        classified: list of Transaction objects from engine output.
        routing_table: ordered list of routing entries (see module docstring).
        marker_account: qb_account value that flags a txn as needing routing.

    Returns:
        (assignments, review_indices, audit_lines)
        - assignments: list of StormwaterAssignment to apply to classified[]
        - review_indices: indices that couldn't be routed (group size mismatch)
        - audit_lines: human-readable log lines
    """
    assignments: List[StormwaterAssignment] = []
    review_indices: List[int] = []
    audit_lines: List[str] = []

    # Group indices by date
    groups_by_date = defaultdict(list)
    for i, txn in enumerate(classified):
        if txn.qb_account == marker_account:
            groups_by_date[txn.date].append(i)

    if not groups_by_date:
        return assignments, review_indices, audit_lines

    expected_size = len(routing_table)

    for d in sorted(groups_by_date.keys()):
        indices = groups_by_date[d]
        size = len(indices)

        if size != expected_size:
            audit_lines.append(
                f"  {d}: {size} bill(s) found but routing table expects {expected_size} — sending to review"
            )
            review_indices.extend(indices)
            continue

        audit_lines.append(f"  {d}: routing {size} bills to {[r['account'] for r in routing_table]}")
        for idx, route in zip(indices, routing_table):
            assignments.append(StormwaterAssignment(
                txn_index=idx,
                qb_account=route["account"],
                qb_class=route.get("class") or "",
                transaction_type=route.get("type", "Asset"),
                classified_by=f"stormwater_pass[{route['account']}]",
                description_suffix=route.get("notes", ""),
            ))

    return assignments, review_indices, audit_lines
