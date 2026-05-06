"""
Loan Payments Loader

Reads loan history CSVs and produces split Transactions for principal,
interest, and (optionally) escrow components of each payment.

Two formats supported:
  1. PCB format: header preamble lines, columns include
     "Amount Credit, ..., Principal, Interest"
  2. Fay format: no preamble, columns include
     "Date, Due Date, Eff Date, Tran Amt, Principal, Interest, Escrow, ..."

For each loan payment, this loader returns 2-3 LoanSplit objects:
  - 1 principal Transaction (Liability account = Loan {loan_num})
  - 1 interest Transaction (Expense if stabilized; capitalized to property
    asset if pre-stab)
  - 0-1 escrow Transaction (asset; only Fay loans have escrow)

Used by run_reconcile.py to replace each matched loan payment in the
bank CSV with its split components.
"""

import csv
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional


@dataclass
class LoanSplit:
    """One component of a loan payment split."""
    loan_num: str
    txn_date: date
    component: str        # "principal", "interest", or "escrow"
    amount: Decimal       # negative (money out)
    description: str      # human-readable
    property_class: str   # the property the loan is for


def _parse_date(raw: str) -> date:
    raw = raw.strip()
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Could not parse date {raw!r}")


def _clean_amount(raw) -> Optional[Decimal]:
    """Parse amount strings like '$1,234.56', '258.22', '-258.22', or empty."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s == "0":
        return Decimal("0")
    # Strip $, commas, %, whitespace
    s = s.replace("$", "").replace(",", "").replace("%", "").strip()
    if not s:
        return None
    # Handle parens-as-negative
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return Decimal(s)
    except Exception:
        return None


def _detect_format(csv_path: Path) -> str:
    """Detect whether CSV is 'pcb' or 'fay' format by inspecting header."""
    with csv_path.open("r", encoding="utf-8") as f:
        first_line = f.readline().strip()
    # PCB format starts with "Account Name : ..."
    if first_line.startswith("Account Name"):
        return "pcb"
    # Fay format starts with "Date,Due Date,Eff Date,..."
    if first_line.startswith("Date,Due Date") or first_line.startswith("Date,"):
        return "fay"
    raise ValueError(f"Unknown loan CSV format. First line: {first_line!r}")


def parse_pcb_loan_csv(csv_path: Path, loan_num: str, property_class: str) -> list:
    """Parse PCB-format loan CSV. Returns list of LoanSplit objects."""
    with csv_path.open("r", encoding="utf-8") as f:
        # Skip preamble lines until we hit the header
        reader = csv.reader(f)
        rows = list(reader)

    # Find header row (contains "Date" and "Principal")
    header_idx = None
    for i, row in enumerate(rows):
        if any("Date" == cell.strip() for cell in row) and \
           any("Principal" in cell for cell in row):
            header_idx = i
            break
    if header_idx is None:
        raise ValueError(f"No header row found in {csv_path}")

    header = [h.strip() for h in rows[header_idx]]
    col = {name: header.index(name) for name in header}

    splits = []
    for row in rows[header_idx + 1:]:
        if not row or not row[col["Date"]].strip():
            continue
        try:
            d = _parse_date(row[col["Date"]])
        except ValueError:
            continue

        prin = _clean_amount(row[col["Principal"]])
        intr = _clean_amount(row[col["Interest"]])

        if prin is not None and prin != 0:
            splits.append(LoanSplit(
                loan_num=loan_num,
                txn_date=d,
                component="principal",
                amount=abs(prin) * -1,  # ensure negative
                description=f"Loan #{loan_num} principal",
                property_class=property_class,
            ))
        if intr is not None and intr != 0:
            splits.append(LoanSplit(
                loan_num=loan_num,
                txn_date=d,
                component="interest",
                amount=abs(intr) * -1,
                description=f"Loan #{loan_num} interest",
                property_class=property_class,
            ))
    return splits


def parse_fay_loan_csv(csv_path: Path, loan_num: str, property_class: str) -> list:
    """Parse Fay-format loan CSV. Returns list of LoanSplit objects."""
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    splits = []
    for row in rows:
        date_raw = (row.get("Date") or "").strip()
        if not date_raw:
            continue
        try:
            d = _parse_date(date_raw)
        except ValueError:
            continue

        prin = _clean_amount(row.get("Principal"))
        intr = _clean_amount(row.get("Interest"))
        escrow = _clean_amount(row.get("Escrow"))

        if prin is not None and prin != 0:
            splits.append(LoanSplit(
                loan_num=loan_num,
                txn_date=d,
                component="principal",
                amount=abs(prin) * -1,
                description=f"Loan #{loan_num} principal",
                property_class=property_class,
            ))
        if intr is not None and intr != 0:
            splits.append(LoanSplit(
                loan_num=loan_num,
                txn_date=d,
                component="interest",
                amount=abs(intr) * -1,
                description=f"Loan #{loan_num} interest",
                property_class=property_class,
            ))
        if escrow is not None and escrow != 0:
            splits.append(LoanSplit(
                loan_num=loan_num,
                txn_date=d,
                component="escrow",
                amount=abs(escrow) * -1,
                description=f"Loan #{loan_num} escrow",
                property_class=property_class,
            ))
    return splits


def load_loan_splits(csv_path: Path, loan_num: str, property_class: str) -> list:
    """Detect format and parse loan CSV. Returns list of LoanSplit objects."""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Loan CSV not found: {csv_path}")
    fmt = _detect_format(csv_path)
    if fmt == "pcb":
        return parse_pcb_loan_csv(csv_path, loan_num, property_class)
    elif fmt == "fay":
        return parse_fay_loan_csv(csv_path, loan_num, property_class)
    else:
        raise ValueError(f"Unsupported loan CSV format: {fmt}")


def load_all_loans(loans_config: dict, base_dir: Path) -> dict:
    """
    Load splits for all loans in the LOANS config.
    
    Args:
      loans_config: dict like LOANS in rules/gj_holdings.py
      base_dir: directory containing the loan CSVs
    
    Returns:
      dict mapping loan_num -> list of LoanSplit objects
    """
    base_dir = Path(base_dir)
    out = {}
    for loan_num, cfg in loans_config.items():
        csv_name = cfg.get("loan_csv")
        if not csv_name:
            continue
        csv_path = base_dir / csv_name
        if not csv_path.exists():
            print(f"  WARNING: loan CSV not found: {csv_path}")
            out[loan_num] = []
            continue
        splits = load_loan_splits(csv_path, loan_num, cfg["property"])
        out[loan_num] = splits
        print(f"  Loan {loan_num} ({cfg['property']}): {len(splits)} split rows from {csv_name}")
    return out


# -------------------- CLI test --------------------

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from rules import gj_holdings

    base = Path("/Users/Josh/Documents/Letters to be printed/Properties/Standard Bus. Docs/Bookkeeping/Bank Accounts/GJ Holdings")
    print(f"Loading all GJ Holdings loans from {base}")
    print()

    all_splits = load_all_loans(gj_holdings.LOANS, base)

    print()
    for loan_num, splits in all_splits.items():
        print(f"--- Loan {loan_num} ---")
        for s in splits:
            print(f"  {s.txn_date} {s.component:10s} ${s.amount:>10,.2f}  {s.description}")
        total_prin = sum(s.amount for s in splits if s.component == "principal")
        total_int = sum(s.amount for s in splits if s.component == "interest")
        total_esc = sum(s.amount for s in splits if s.component == "escrow")
        print(f"  TOTALS: prin={total_prin:.2f}, int={total_int:.2f}, escrow={total_esc:.2f}")
        print()
