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
    """Parse PCB-format loan CSV. Returns list of LoanSplit objects.

    Handles three header shapes:
      1. Date + Principal + Interest (standard amortizing loan)
      2. Date + Interest only (interest-only construction loan, no principal column)
      3. Date + Principal + Interest + Escrow (loans with escrow)

    LIP Disbursement rows (negative Amount Debit, no interest/principal) are
    netted against same-day regular payments for interest-only loans.
    """
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    # Find header row — must have "Date" AND at least one of Principal/Interest
    header_idx = None
    for i, row in enumerate(rows):
        cells = [c.strip() for c in row]
        if "Date" in cells and ("Principal" in cells or "Interest" in cells):
            header_idx = i
            break
    if header_idx is None:
        raise ValueError(f"No header row found in {csv_path}")

    header = [h.strip() for h in rows[header_idx]]
    col = {name: header.index(name) for name in header}
    has_principal = "Principal" in col
    has_interest = "Interest" in col
    has_escrow = "Escrow" in col
    # LIP disbursements show up in Amount Debit column
    amt_debit_col = col.get("Amount Debit")

    # First pass: collect raw rows by date so we can net LIP against payments
    raw_by_date = {}
    for row in rows[header_idx + 1:]:
        if not row or len(row) <= col["Date"] or not row[col["Date"]].strip():
            continue
        try:
            d = _parse_date(row[col["Date"]])
        except ValueError:
            continue

        prin = _clean_amount(row[col["Principal"]]) if has_principal else None
        intr = _clean_amount(row[col["Interest"]]) if has_interest else None
        escr = _clean_amount(row[col["Escrow"]]) if has_escrow else None
        debit = _clean_amount(row[amt_debit_col]) if amt_debit_col is not None else None

        raw_by_date.setdefault(d, []).append({
            "principal": prin, "interest": intr, "escrow": escr, "debit": debit,
        })

    splits = []
    is_interest_only = not has_principal

    for d, entries in sorted(raw_by_date.items()):
        if is_interest_only:
            # Net LIP disbursements (negative debit, no interest) against
            # regular interest payments to capitalize the net amount.
            total_interest = sum(
                (e["interest"] for e in entries if e["interest"] is not None),
                Decimal("0"),
            )
            total_lip = sum(
                (e["debit"] for e in entries
                 if e["debit"] is not None and e["debit"] < 0 and not e["interest"]),
                Decimal("0"),
            )
            # Net amount to capitalize: |interest| + lip (lip is already negative)
            net = abs(total_interest) + total_lip
            if net != 0:
                splits.append(LoanSplit(
                    loan_num=loan_num,
                    txn_date=d,
                    component="interest",
                    amount=abs(net) * -1,
                    description=f"Loan #{loan_num} interest (net of LIP)" if total_lip else f"Loan #{loan_num} interest",
                    property_class=property_class,
                ))
        else:
            # Standard: emit principal + interest + escrow rows independently
            for e in entries:
                if e["principal"] is not None and e["principal"] != 0:
                    splits.append(LoanSplit(
                        loan_num=loan_num,
                        txn_date=d,
                        component="principal",
                        amount=abs(e["principal"]) * -1,
                        description=f"Loan #{loan_num} principal",
                        property_class=property_class,
                    ))
                if e["interest"] is not None and e["interest"] != 0:
                    splits.append(LoanSplit(
                        loan_num=loan_num,
                        txn_date=d,
                        component="interest",
                        amount=abs(e["interest"]) * -1,
                        description=f"Loan #{loan_num} interest",
                        property_class=property_class,
                    ))
                if e["escrow"] is not None and e["escrow"] != 0:
                    splits.append(LoanSplit(
                        loan_num=loan_num,
                        txn_date=d,
                        component="escrow",
                        amount=abs(e["escrow"]) * -1,
                        description=f"Loan #{loan_num} escrow",
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


def get_loan_ending_balances(loans_config, pcb_dir):
    """Read each loan CSV's most recent Balance (first data row; PCB exports
    are reverse-chronological). Returns {loan_num: float_balance}."""
    import csv as _csv
    balances = {}
    for loan_num, cfg in loans_config.items():
        csv_name = cfg.get("loan_csv")
        if not csv_name:
            continue
        path = pcb_dir / csv_name
        if not path.exists():
            continue
        try:
            with open(path, newline="", encoding="utf-8-sig") as f:
                rows = list(_csv.reader(f))
            header_i = next(i for i, r in enumerate(rows) if r and r[0].strip().startswith("Transaction Number"))
            for r in rows[header_i + 1:]:
                if len(r) > 6 and r[6].strip():
                    balances[loan_num] = float(r[6].replace(",", ""))
                    break
        except Exception:
            continue
    return balances
