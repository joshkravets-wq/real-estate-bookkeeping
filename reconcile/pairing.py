"""
Reversal pairing logic for PCB transactions.

PCB's CSV exports include three patterns that need to be netted out before
the rules engine sees the data:

  1. Bounced-and-retried payments: original withdrawal + 'Rejected Transaction'
     reversal of equal/opposite amount within ~7 days. Both rows are dropped.

  2. NSF fees that the bank later waived: 'Insufficient Funds Charge' debit
     ($35) followed by a 'Rejected Transaction' credit ($35) within ~3 days.
     Both rows are dropped. When multiple NSFs could match a single reversal,
     the MOST RECENT NSF is paired (LIFO).

  3. NSF fees that stuck (no reversal): kept as real Bank Service Charges.

After this pass runs, the remaining transactions are the net economic
events that go through the rules engine for classification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import List, Optional, Tuple

try:
    from reconcile.parsers.pcb_csv import Transaction
except ImportError:
    from pcb_csv import Transaction


REVERSAL_LOOKBACK_DAYS = 7
NSF_REVERSAL_LOOKAHEAD_DAYS = 3


@dataclass
class PairingResult:
    kept: List[Transaction] = field(default_factory=list)
    dropped: List[Tuple[Transaction, str]] = field(default_factory=list)
    audit_notes: List[str] = field(default_factory=list)


def _is_reversal(txn):
    desc = (txn.description or "").lower()
    return "rejected transaction" in desc


def _is_nsf_charge(txn):
    desc = (txn.description or "").lower()
    return "insufficient funds charge" in desc and txn.amount < 0


def _looks_like_nsf_reversal(candidate_reversal, all_txns, used_indices):
    earliest = candidate_reversal.txn_date - timedelta(days=NSF_REVERSAL_LOOKAHEAD_DAYS)
    for idx, t in enumerate(all_txns):
        if idx in used_indices:
            continue
        if t is candidate_reversal:
            continue
        if t.source_account != candidate_reversal.source_account:
            continue
        if not _is_nsf_charge(t):
            continue
        if t.amount != -candidate_reversal.amount:
            continue
        if t.txn_date > candidate_reversal.txn_date:
            continue
        if t.txn_date < earliest:
            continue
        return True
    return False


def _find_reversal_match(reversal, candidates, used_indices):
    target_amount = -reversal.amount
    earliest_date = reversal.txn_date - timedelta(days=REVERSAL_LOOKBACK_DAYS)

    best_idx = None
    best_date = None
    for idx, candidate in enumerate(candidates):
        if idx in used_indices:
            continue
        if candidate is reversal:
            continue
        if candidate.source_account != reversal.source_account:
            continue
        if candidate.amount != target_amount:
            continue
        if candidate.txn_date > reversal.txn_date:
            continue
        if candidate.txn_date < earliest_date:
            continue
        if _is_reversal(candidate):
            continue
        if best_date is None or candidate.txn_date > best_date:
            best_date = candidate.txn_date
            best_idx = idx

    return best_idx


def pair_reversals(transactions):
    result = PairingResult()
    used_indices = set()

    txns = sorted(transactions, key=lambda t: (t.txn_date, t.source_account))

    # Pass 1: pair 'Rejected Transaction' reversals with their originals.
    for idx, txn in enumerate(txns):
        if idx in used_indices:
            continue
        if not _is_reversal(txn):
            continue

        is_nsf_reversal = (
            txn.amount > 0 and txn.amount == Decimal("35")
            and _looks_like_nsf_reversal(txn, txns, used_indices)
        )
        if is_nsf_reversal:
            continue

        match_idx = _find_reversal_match(txn, txns, used_indices)
        if match_idx is None:
            result.audit_notes.append(
                f"WARN: Stray reversal with no match: {txn.txn_date} "
                f"{txn.source_account} {txn.amount} '{txn.description}'"
            )
            continue

        original = txns[match_idx]
        used_indices.add(idx)
        used_indices.add(match_idx)
        result.dropped.append((original, f"Reversed by {txn.txn_date} '{txn.description}'"))
        result.dropped.append((txn, f"Reversal of {original.txn_date} '{original.description}'"))
        result.audit_notes.append(
            f"PAIRED reversal: {original.txn_date} {original.amount} "
            f"<-> {txn.txn_date} {txn.amount} (account {txn.source_account})"
        )

    # Pass 2: pair NSF fees with reversals (LIFO matching).
    nsf_reversals = [
        (idx, t) for idx, t in enumerate(txns)
        if idx not in used_indices
        and _is_reversal(t)
        and t.amount == Decimal("35")
    ]

    for rev_idx, reversal in nsf_reversals:
        if rev_idx in used_indices:
            continue
        earliest = reversal.txn_date - timedelta(days=NSF_REVERSAL_LOOKAHEAD_DAYS)
        best_nsf_idx = None
        best_nsf_date = None
        for nsf_idx, candidate in enumerate(txns):
            if nsf_idx in used_indices:
                continue
            if not _is_nsf_charge(candidate):
                continue
            if candidate.source_account != reversal.source_account:
                continue
            if candidate.amount != -reversal.amount:
                continue
            if candidate.txn_date > reversal.txn_date:
                continue
            if candidate.txn_date < earliest:
                continue
            if best_nsf_date is None or candidate.txn_date > best_nsf_date:
                best_nsf_date = candidate.txn_date
                best_nsf_idx = nsf_idx

        if best_nsf_idx is None:
            result.audit_notes.append(
                f"WARN: $35 reversal with no NSF match: {reversal.txn_date} "
                f"{reversal.source_account} '{reversal.description}'"
            )
            continue

        nsf = txns[best_nsf_idx]
        used_indices.add(rev_idx)
        used_indices.add(best_nsf_idx)
        result.dropped.append((nsf, f"NSF reversed by {reversal.txn_date}"))
        result.dropped.append((reversal, f"NSF reversal of {nsf.txn_date}"))
        result.audit_notes.append(
            f"PAIRED NSF (most-recent): {nsf.txn_date} {nsf.amount} "
            f"<-> {reversal.txn_date} {reversal.amount} "
            f"(account {nsf.source_account})"
        )

    # Note any NSFs that stuck
    for idx, txn in enumerate(txns):
        if idx in used_indices:
            continue
        if not _is_nsf_charge(txn):
            continue
        result.audit_notes.append(
            f"NSF KEPT (no reversal within {NSF_REVERSAL_LOOKAHEAD_DAYS}d): "
            f"{txn.txn_date} {txn.source_account} {txn.amount} "
            f"'{txn.description}' -> Bank Service Charges"
        )

    # Pass 3: collect everything not used
    for idx, txn in enumerate(txns):
        if idx not in used_indices:
            result.kept.append(txn)

    return result


if __name__ == "__main__":
    import sys
    from pathlib import Path

    if len(sys.argv) < 2:
        print("Usage: python pairing.py <csv_file_or_directory>")
        sys.exit(1)

    target = Path(sys.argv[1])

    try:
        from reconcile.parsers.pcb_csv import parse_pcb_csv, parse_pcb_csv_directory
    except ImportError:
        from pcb_csv import parse_pcb_csv, parse_pcb_csv_directory

    if target.is_dir():
        txns = parse_pcb_csv_directory(target)
    else:
        txns = parse_pcb_csv(target)

    print(f"Parsed {len(txns)} raw transactions")
    print()

    result = pair_reversals(txns)

    print(f"After pairing:")
    print(f"  Kept:    {len(result.kept)} transactions (go to rules engine)")
    print(f"  Dropped: {len(result.dropped)} transactions (paired non-events)")
    print()
    print("=" * 70)
    print("AUDIT NOTES")
    print("=" * 70)
    for note in result.audit_notes:
        print(f"  {note}")
    print()
    print("=" * 70)
    print("DROPPED TRANSACTIONS")
    print("=" * 70)
    for txn, reason in result.dropped:
        print(f"  {txn.txn_date} {txn.source_account} {txn.amount:>12} '{txn.description[:60]}'")
        print(f"      -> {reason}")
    print()
    print("=" * 70)
    print(f"KEPT TRANSACTIONS ({len(result.kept)})")
    print("=" * 70)
    for t in result.kept:
        print(f"  {t.txn_date} {t.source_account} {t.amount:>12} {t.description[:80]}")
