"""
Manual Overrides loader.

Reads the Manual Overrides Google Sheet (in Bookkeeping Processors folder)
and provides per-transaction accounting overrides. Each row in the sheet is
an explicit, audited accounting decision that supersedes all engine logic.

Sheet schema:
    Date | Account | Amount | Description Match | QB Account | Class |
    Approved By | Approved Date | Notes

Matching:
    Override applies to a transaction when ALL of the following match:
    - txn.date == override.date  (exact)
    - txn.source_account == override.account  (exact)
    - txn.amount == override.amount  (within $0.01)
    - override.description_match (lowercased) appears in txn.description (lowercased)

If multiple override rows match the same txn, the FIRST match wins (earliest
row in the sheet). Future improvement: flag ambiguity.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from reconcile.drive_client import DriveClient


@dataclass
class Override:
    row_num: int
    txn_date: date
    account: str
    amount: float
    description_match: str
    qb_account: str
    qb_class: Optional[str]
    approved_by: str
    approved_date: Optional[date]
    notes: str
    is_off_bank_journal: bool = False


def _parse_date(value):
    """Parse date from Google Sheets cell value."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Could not parse date: {value!r}")


def _parse_amount(value):
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace("$", "").replace(",", "")
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    return float(s)


def load_overrides(file_id):
    """Load all override rows from the Manual Overrides sheet."""
    client = DriveClient()
    wb = client.fetch_spreadsheet(file_id)
    sheet = wb.active

    overrides = []
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        return overrides

    # Header row should be row 1
    header = [str(c or "").strip().lower() for c in rows[0]]
    expected = ["date", "account", "amount", "description match", "qb account",
                "class", "approved by", "approved date", "notes"]
    for exp in expected:
        if exp not in header:
            raise ValueError(
                f"Manual Overrides sheet missing expected column '{exp}'. "
                f"Found columns: {header}"
            )

    # Index columns
    col = {h: i for i, h in enumerate(header)}
    # Optional: off-bank journal column. When truthy, the row emits unconditionally
    # as a synthetic classified transaction (no bank match required).
    off_bank_col = col.get("off-bank journal")

    for row_num, row in enumerate(rows[1:], start=2):
        # Skip empty rows
        if all(c is None or c == "" for c in row):
            continue

        try:
            txn_date = _parse_date(row[col["date"]])
            account = str(row[col["account"]] or "").strip()
            amount = _parse_amount(row[col["amount"]])
            desc_match = str(row[col["description match"]] or "").strip()
            qb_account = str(row[col["qb account"]] or "").strip()
            qb_class = str(row[col["class"]] or "").strip() or None
            approved_by = str(row[col["approved by"]] or "").strip()
            approved_date = _parse_date(row[col["approved date"]])
            notes = str(row[col["notes"]] or "").strip()
        except (ValueError, IndexError) as e:
            print(f"  WARNING: row {row_num} skipped ({type(e).__name__}: {e})")
            continue

        if txn_date is None or amount is None or not account:
            print(f"  WARNING: row {row_num} skipped (missing required field)")
            continue

        # Detect off-bank journal flag (truthy string in the optional column)
        is_off_bank = False
        if off_bank_col is not None and off_bank_col < len(row):
            raw_flag = row[off_bank_col]
            if raw_flag is not None:
                flag_str = str(raw_flag).strip().lower()
                is_off_bank = flag_str in ("x", "y", "yes", "true", "1", "✓", "journal")

        overrides.append(Override(
            row_num=row_num,
            txn_date=txn_date,
            account=account,
            amount=amount,
            description_match=desc_match,
            qb_account=qb_account,
            qb_class=qb_class,
            approved_by=approved_by,
            approved_date=approved_date,
            notes=notes,
            is_off_bank_journal=is_off_bank,
        ))

    return overrides


def find_override(txn, overrides, used_overrides=None):
    """Find the first unused override matching this transaction.
    
    Args:
        txn: The transaction to match.
        overrides: List of override candidates.
        used_overrides: Optional set of override row_nums already consumed.
            Pass the same set across calls to avoid double-matching.
    
    Returns the matching Override or None.
    """
    txn_desc_lower = (txn.description or "").lower()
    txn_acct = (txn.source_account or "").strip()

    for ov in overrides:
        if used_overrides is not None and ov.row_num in used_overrides:
            continue
        if ov.txn_date != txn.date:
            continue
        if ov.account != txn_acct:
            continue
        if abs(ov.amount - txn.amount) > 0.01:
            continue
        if ov.description_match and ov.description_match.lower() not in txn_desc_lower:
            continue
        if used_overrides is not None:
            used_overrides.add(ov.row_num)
        return ov

    return None


if __name__ == "__main__":
    # Smoke test: load and print all overrides
    from rules.properties_registry import MANUAL_OVERRIDES_FILE_ID

    print(f"Loading Manual Overrides from {MANUAL_OVERRIDES_FILE_ID}...")
    overrides = load_overrides(MANUAL_OVERRIDES_FILE_ID)
    print(f"Loaded {len(overrides)} overrides")
    print()
    for ov in overrides:
        print(f"  row {ov.row_num}: {ov.txn_date} {ov.account} ${ov.amount:>10.2f}")
        print(f"    description_match: {ov.description_match!r}")
        print(f"    -> {ov.qb_account} / {ov.qb_class}")
        print(f"    approved_by: {ov.approved_by} on {ov.approved_date}")
        print(f"    notes: {ov.notes}")
        print()


def get_off_bank_journals(overrides):
    """Return only the Override rows marked as off-bank journals.

    These rows are emitted unconditionally as synthetic classified transactions
    — they do NOT need to match a bank transaction. Used for sale clearing
    journals, refinance journals, and other accounting entries that don't
    appear in any bank CSV.
    """
    return [ov for ov in overrides if ov.is_off_bank_journal]
