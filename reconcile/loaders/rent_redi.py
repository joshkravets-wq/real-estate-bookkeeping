"""
RentRedi Loader

Reads the shared RentRedi deposits CSV (covers all entities) and
produces grouped deposit objects filtered to a specific bank suffix.

CSV structure: each "Sweep ID" groups one bank deposit and N rent line
items. The Deposit row has the total in column 1; subsequent rows have
$0 in column 1 but show "$X" in "Amount Paid" column with property/unit/tenant
detail.

Usage:
  deposits = load_rentredi_deposits(csv_path, bank_suffix="3395")
  for d in deposits:
    print(f"{d.deposit_date} ${d.total} -> {len(d.rents)} rents")
    for r in d.rents:
      print(f"  ${r.amount} - {r.property} {r.unit} - {r.tenant}")
"""

import csv
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional


@dataclass
class RentLineItem:
    amount: Decimal
    property: str
    unit: str
    tenant: str
    rent_date: date          # date the rent was due/paid
    description: str         # "Rent", "Rent + Late Fee", "Rent (prorated)", etc.


@dataclass
class RentRediDeposit:
    """A grouped RentRedi deposit: 1 bank line + N rent line items."""
    deposit_date: date
    total: Decimal
    bank_suffix: str
    sweep_id: str
    rents: list = field(default_factory=list)


def _parse_date(raw: str) -> Optional[date]:
    raw = raw.strip()
    if not raw:
        return None
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _clean_amount(raw) -> Optional[Decimal]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    # Parenthesized amounts are negative: "($646.00)" -> -646.00
    negative = s.startswith("(") and s.endswith(")")
    if negative:
        s = s[1:-1]
    # Strip $, commas, whitespace
    s = s.replace("$", "").replace(",", "").strip()
    if not s:
        return None
    try:
        d = Decimal(s)
        return -d if negative else d
    except Exception:
        return None


def load_rentredi_deposits(csv_path, bank_suffix: str) -> list:
    """
    Parse RentRedi deposits CSV and return RentRediDeposit objects
    filtered to the specified bank suffix.
    
    Args:
      csv_path: path to the RentRedi CSV
      bank_suffix: last-4 of bank account (e.g., "3395")
    
    Returns:
      list of RentRediDeposit objects, sorted by deposit_date
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"RentRedi CSV not found: {csv_path}")

    target_suffix = f"xxxx{bank_suffix}"
    deposits_by_sweep = {}

    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sweep_id = (row.get("Sweep ID") or "").strip()
            if not sweep_id:
                continue

            bank = (row.get("Deposited to bank ending in") or "").strip()
            if bank != target_suffix:
                continue

            deposit_date = _parse_date(row.get("Expected Funds Available", ""))
            if not deposit_date:
                continue

            description = (row.get("Description") or "").strip()
            deposit_total_raw = row.get("Deposit/Withdrawal", "").strip()
            rent_amount_raw = row.get("Amount Paid", "").strip()

            if description == "Deposit" and deposit_total_raw:
                # Deposit header row — set the total
                total = _clean_amount(deposit_total_raw)
                if total is None:
                    continue
                if sweep_id not in deposits_by_sweep:
                    deposits_by_sweep[sweep_id] = RentRediDeposit(
                        deposit_date=deposit_date,
                        total=total,
                        bank_suffix=bank_suffix,
                        sweep_id=sweep_id,
                        rents=[],
                    )
                else:
                    # Already created by a rent row; just set total
                    deposits_by_sweep[sweep_id].total = total
                    deposits_by_sweep[sweep_id].deposit_date = deposit_date
            elif rent_amount_raw:
                # Rent line item
                amt = _clean_amount(rent_amount_raw)
                if amt is None:
                    continue
                rent_date = _parse_date(row.get("Date", ""))
                rent = RentLineItem(
                    amount=amt,
                    property=(row.get("Property") or "").strip(),
                    unit=(row.get("Unit") or "").strip(),
                    tenant=(row.get("Tenant") or "").strip(),
                    rent_date=rent_date or deposit_date,
                    description=description or "Rent",
                )
                if sweep_id not in deposits_by_sweep:
                    # Create deposit shell; total will come later
                    deposits_by_sweep[sweep_id] = RentRediDeposit(
                        deposit_date=deposit_date,
                        total=Decimal("0"),  # placeholder
                        bank_suffix=bank_suffix,
                        sweep_id=sweep_id,
                        rents=[rent],
                    )
                else:
                    deposits_by_sweep[sweep_id].rents.append(rent)

    # Filter out deposits where total is 0 (shouldn't happen for legit deposits)
    deposits = [d for d in deposits_by_sweep.values() if d.total > 0]

    # Balancing line: when itemized rents don't sum to the sweep total
    # (RentRedi processor fees on reversals aren't itemized), add a small
    # adjustment line so split rows conserve money vs the bank deposit.
    for d in deposits:
        if not d.rents:
            continue
        diff = d.total - sum(r.amount for r in d.rents)
        if diff != 0 and abs(diff) <= Decimal("25"):
            anchor = max(d.rents, key=lambda r: abs(r.amount))
            d.rents.append(RentLineItem(
                amount=diff,
                property=anchor.property,
                unit=anchor.unit,
                tenant=anchor.tenant,
                rent_date=d.deposit_date,
                description="RentRedi fee/adjustment",
            ))

    # Sort by deposit_date
    deposits.sort(key=lambda d: d.deposit_date)

    return deposits


def find_deposit_for_bank_txn(deposits: list, txn_date: date, txn_amount: Decimal,
                               date_tolerance_days: int = 2,
                               amount_tolerance: Decimal = Decimal("0.50")) -> Optional[RentRediDeposit]:
    """
    Find the RentRediDeposit matching a given bank transaction.
    
    Returns the deposit if found, else None.
    """
    from datetime import timedelta
    target_amount = abs(txn_amount)
    earliest = txn_date - timedelta(days=date_tolerance_days)
    latest = txn_date + timedelta(days=date_tolerance_days)

    for d in deposits:
        if not (earliest <= d.deposit_date <= latest):
            continue
        if abs(d.total - target_amount) <= amount_tolerance:
            return d
    return None


# -------------------- CLI test --------------------

if __name__ == "__main__":
    csv_path = Path("/Users/Josh/Documents/Letters to be printed/Properties/Standard Bus. Docs/Bookkeeping/Bank Accounts/Rent Redi Deposits Jan-march.csv")
    print(f"Loading RentRedi deposits from {csv_path}")
    print()

    deposits = load_rentredi_deposits(csv_path, bank_suffix="3395")
    print(f"Loaded {len(deposits)} GJ Holdings (xxxx3395) deposits")
    print()

    total_amount = sum(d.total for d in deposits)
    print(f"Total deposited: ${total_amount:,.2f}")
    print()

    print("Deposits:")
    for d in deposits:
        print(f"  {d.deposit_date} ${d.total:>9,.2f}  ({len(d.rents)} rents) {d.sweep_id[:25]}")
        for r in d.rents:
            print(f"    ${r.amount:>9,.2f}  {r.property[:20]:20s} {r.unit[:5]:5s} {r.description[:25]:25s} {r.tenant}")
