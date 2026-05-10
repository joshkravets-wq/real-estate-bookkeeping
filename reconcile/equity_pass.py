"""
Equity Assignment Pass

Detects clusters of equal-amount equity transactions (capital contributions
or distributions) within a 14-day window and assigns each to a member in
fixed order.

Rules:
- Cluster size must equal number of members (typically 4)
- All amounts must be equal (within $0.01)
- All transactions must fall within ROLLING_WINDOW_DAYS of each other
- Deposits (positive amounts) -> Capital:Contribution per member
- Withdrawals (negative amounts) -> Capital:Draws per member

Member assignment order is fixed (taken from rules_module.ENTITY config).
The order doesn\'t matter for year-end totals since members contribute equally;
this just lets the engine produce reasonable per-row attribution.

Limitations:
- Single-member contributions (e.g., Boris $7k alone) won\'t be detected
  -> remain in review queue for Manual Override
- Mixed clusters (e.g., 4 contributions of varying amounts) won\'t be
  detected -> remain in review queue
- Within a cluster, the engine assigns deterministically; if the actual
  payer differs from the assignment, member-level totals will be off but
  entity-level equity total stays correct (since contributions are equal)
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta


ROLLING_WINDOW_DAYS = 14
DEFAULT_ROUND_AMOUNTS = [1000, 2000, 5000, 7000, 10000, 18000, 25000, 27719, 50000]


@dataclass
class EquityAssignment:
    txn_index: int
    qb_account: str
    qb_class: str
    transaction_type: str
    classified_by: str


def find_equity_clusters(transactions, members, window_days=ROLLING_WINDOW_DAYS):
    """
    Find groups of equal-amount equity transactions within a time window.
    
    Args:
      transactions: list of Transaction objects
      members: list of member names (defines cluster size)
      window_days: max days between any two txns in a cluster
    
    Returns:
      list of clusters; each cluster is a list of (txn_index, txn) tuples
    """
    cluster_size = len(members)
    
    # Find candidate equity transactions: round-number amounts, descriptions
    # that look like deposits or large checks
    candidates = []
    for i, t in enumerate(transactions):
        amt = abs(t.amount)
        # Skip if already classified to a non-ASK account
        if t.qb_account and t.qb_account not in ("ASK", "RENTREDI_NO_MATCH"):
            # Already classified by another rule; skip
            continue
        
        desc_upper = (t.description or "").upper()
        is_deposit = t.amount > 0 and ("DEPOSIT" in desc_upper or "MOBILE" in desc_upper)
        is_check = t.amount < 0 and "CHECK" in desc_upper
        
        if not (is_deposit or is_check):
            continue
        
        # Round-number heuristic
        if amt < 1000:
            continue
        if amt != round(amt):
            continue
        
        candidates.append((i, t))
    
    # Group by amount
    by_amount = defaultdict(list)
    for i, t in candidates:
        # Use signed amount as key (deposits and checks should not cluster together)
        by_amount[float(t.amount)].append((i, t))
    
    # For each amount group, find clusters of cluster_size within window_days
    clusters = []
    for amt, group in by_amount.items():
        if len(group) < cluster_size:
            continue
        
        # Sort by date
        group.sort(key=lambda x: x[1].date)
        
        # Sliding window: find any subset of cluster_size within window_days
        used = set()
        for start_idx in range(len(group) - cluster_size + 1):
            if start_idx in used:
                continue
            window_start = group[start_idx][1].date
            window_end = window_start + timedelta(days=window_days)
            
            # Take all txns in this window
            window = [(i, t) for i, t in group[start_idx:] if t.date <= window_end]
            
            # If we have exactly cluster_size or more, take the first cluster_size
            if len(window) >= cluster_size:
                cluster = window[:cluster_size]
                clusters.append(cluster)
                # Mark indices as used
                for j in range(start_idx, start_idx + cluster_size):
                    used.add(j)
    
    return clusters


def assign_equity_clusters(transactions, members, equity_accounts, window_days=ROLLING_WINDOW_DAYS):
    """
    Find equity clusters and assign each txn in a cluster to a member.
    
    Args:
      transactions: list of Transaction objects
      members: ordered list of member names (e.g., ["Steve Kravets", ...])
      equity_accounts: dict mapping member name -> {"contribution": "...", "draws": "..."}
      window_days: max date span for a cluster
    
    Returns:
      (assignments: list of EquityAssignment,
       audit_log: list of strings)
    """
    audit = []
    
    clusters = find_equity_clusters(transactions, members, window_days)
    audit.append(f"Found {len(clusters)} equity clusters of {len(members)} txns each")
    
    assignments = []
    for cluster_idx, cluster in enumerate(clusters):
        # Sort by date for deterministic assignment
        cluster_sorted = sorted(cluster, key=lambda x: x[1].date)
        
        amount = cluster_sorted[0][1].amount
        is_contribution = amount > 0
        date_range = f"{cluster_sorted[0][1].date} to {cluster_sorted[-1][1].date}"
        kind = "contribution" if is_contribution else "distribution"
        audit.append(f"  Cluster {cluster_idx+1}: ${abs(amount):,.2f} {kind} ({date_range})")
        
        for member_idx, (txn_idx, txn) in enumerate(cluster_sorted):
            member = members[member_idx]
            accounts = equity_accounts.get(member, {})
            
            if is_contribution:
                qb_acct = accounts.get("contribution", f"{member} Capital:Contribution")
                ttype = "Equity"
            else:
                qb_acct = accounts.get("draws", f"{member} Capital:Draws")
                ttype = "Equity"
            
            assignments.append(EquityAssignment(
                txn_index=txn_idx,
                qb_account=qb_acct,
                qb_class="",  # Equity has no class
                transaction_type=ttype,
                classified_by=f"equity_cluster[{kind} \#{cluster_idx+1} -> {member}]",
            ))
            audit.append(f"    {txn.date} ${txn.amount:>10,.2f} -> {qb_acct}")
    
    audit.append(f"Total assigned: {len(assignments)}")
    return assignments, audit
