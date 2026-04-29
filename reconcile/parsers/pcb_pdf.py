"""
Penn Community Bank PDF Statement Parser

Reads PCB monthly statement PDFs and produces Transaction objects
compatible with the reconciliation engine.
"""

import re
from datetime import date
from pathlib import Path
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from reconcile.engine import Transaction


MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def parse_filename(filepath):
    """Extract account number and month from filename like '5494 January.pdf'."""
    name = Path(filepath).stem
    parts = name.split()
    account_num = None
    month_token = None
    for part in parts:
        if part.isdigit() and len(part) == 4:
            account_num = part
        elif part.lower() in MONTH_MAP:
            month_token = part.lower()
    source_account = f"PCB {account_num}" if account_num else None
    month = MONTH_MAP.get(month_token) if month_token else None
    return source_account, month


def parse_amount(text):
    """Parse '$3,000.00' or '$3,000.00-' or '-$1,332.88' into a float."""
    text = text.strip()
    is_negative = False
    if text.endswith("-"):
        is_negative = True
        text = text[:-1]
    if text.startswith("-"):
        is_negative = True
        text = text[1:]
    text = text.replace("$", "").replace(",", "").strip()
    try:
        amt = float(text)
    except ValueError:
        return None
    return -amt if is_negative else amt


def extract_statement_period(text):
    """Find 'From MM/DD/YY' and 'Through MM/DD/YY' in header text."""
    from_match = re.search(r"From\s+(\d{1,2})/(\d{1,2})/(\d{2})", text)
    through_match = re.search(r"Through\s+(\d{1,2})/(\d{1,2})/(\d{2})", text)
    start_date = end_date = None
    if from_match:
        m, d, y = from_match.groups()
        start_date = date(2000 + int(y), int(m), int(d))
    if through_match:
        m, d, y = through_match.groups()
        end_date = date(2000 + int(y), int(m), int(d))
    return start_date, end_date


def extract_account_number(text):
    """Find 'XXXXXXX####' pattern and return last 4 digits."""
    m = re.search(r"X{6,}(\d{4})", text)
    return m.group(1) if m else None


TRANSACTION_LINE_RE = re.compile(r"^(\d{1,2})/(\d{1,2})\s+(.+)$")
AMOUNT_RE = re.compile(r"-?\$[\d,]+\.\d{2}-?")


def parse_transaction_line(line, statement_year):
    """Parse a single transaction line."""
    m = TRANSACTION_LINE_RE.match(line.strip())
    if not m:
        return None
    month_str, day_str, rest = m.groups()
    try:
        month = int(month_str)
        day = int(day_str)
    except ValueError:
        return None

    rest_upper = rest.upper()
    if "BEGINNING BALANCE" in rest_upper or "ENDING BALANCE" in rest_upper:
        return None

    amounts = AMOUNT_RE.findall(rest)
    if not amounts:
        return None

    balance_str = amounts[-1]
    transaction_amount_strs = amounts[:-1]
    if not transaction_amount_strs:
        return None

    txn_amount_str = transaction_amount_strs[0]
    amount = parse_amount(txn_amount_str)
    if amount is None:
        return None

    first_amt_pos = rest.find(transaction_amount_strs[0])
    description = rest[:first_amt_pos].strip()

    txn_date = date(statement_year, month, day)
    return {
        "date": txn_date,
        "description": description,
        "amount": amount,
        "balance_str": balance_str,
        "raw_text": line,
    }


def parse_pcb_pdf(filepath, source_account=None):
    """Parse a PCB monthly statement PDF and return Transaction objects."""
    import pdfplumber

    filepath = Path(filepath)

    if source_account is None:
        source_account, _ = parse_filename(filepath)

    full_text = ""
    page_texts = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            page_texts.append(t)
            full_text += t + "\n"

    start_date, end_date = extract_statement_period(full_text)
    if not start_date:
        raise ValueError(f"Could not find statement period in {filepath}")
    statement_year = start_date.year

    pdf_account = extract_account_number(full_text)
    if source_account and pdf_account and pdf_account not in source_account:
        print(f"WARN: filename says {source_account} but PDF says XXXXXXX{pdf_account}")

    transactions = []
    for page_text in page_texts:
        if "TRANSACTIONS" not in page_text:
            continue

        after_header = page_text.split("TRANSACTIONS", 1)[1]
        if "CHECK REGISTER" in after_header:
            after_header = after_header.split("CHECK REGISTER", 1)[0]
        if "FEE SUMMARY" in after_header:
            after_header = after_header.split("FEE SUMMARY", 1)[0]

        lines = after_header.strip().split("\n")
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            parsed = parse_transaction_line(line, statement_year)

            if parsed:
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    if not next_line:
                        break
                    if TRANSACTION_LINE_RE.match(next_line):
                        break
                    if any(kw in next_line.upper() for kw in [
                        "DATE DESCRIPTION", "BASIC BUSINESS CHECKING",
                        "XXXXXXX", "PAGE ", "TRANSACTIONS"
                    ]):
                        break
                    parsed["description"] = parsed["description"] + " " + next_line
                    j += 1
                i = j

                desc_upper = parsed["description"].upper()
                is_reversal = ("(REVERSE)" in desc_upper or "(REJECTED)" in desc_upper)

                txn = Transaction(
                    source_account=source_account,
                    date=parsed["date"],
                    description=parsed["description"],
                    amount=parsed["amount"],
                    raw_data={
                        "source_pdf": str(filepath),
                        "raw_text": parsed["raw_text"],
                        "balance_after": parsed["balance_str"],
                        "is_reversal": is_reversal,
                    },
                )
                transactions.append(txn)
            else:
                i += 1

    transactions = _mark_reversal_pairs(transactions)
    return transactions


def _mark_reversal_pairs(transactions):
    """Find NSF/check reversal pairs and mark both sides."""
    for i, txn in enumerate(transactions):
        desc_upper = txn.description.upper()

        if "(REVERSE)" in desc_upper:
            target_amt = abs(txn.amount)
            for j in range(max(0, i-5), i):
                other = transactions[j]
                if (abs(other.amount) == target_amt and
                    other.amount < 0 and
                    "INSUFFICIENT FUNDS" in other.description.upper() and
                    not other.raw_data.get("is_reversed", False)):
                    other.raw_data["is_reversed"] = True
                    txn.raw_data["is_reversal_entry"] = True
                    break

        if "(REJECTED)" in desc_upper:
            txn.raw_data["is_reversal_entry"] = True
            target_amt = abs(txn.amount)
            check_match = re.search(r"Check\s+(\d+)", txn.description)
            if check_match:
                check_num = check_match.group(1)
                for j in range(max(0, i-5), i):
                    other = transactions[j]
                    if (abs(other.amount) == target_amt and
                        other.amount < 0 and
                        f"Check {check_num}" in other.description and
                        "(REJECTED)" not in other.description.upper() and
                        not other.raw_data.get("is_reversed", False)):
                        other.raw_data["is_reversed"] = True
                        break

    return transactions


def filter_reversal_entries(transactions):
    """Remove reversal entries and reversed-out charges."""
    return [t for t in transactions
            if not t.raw_data.get("is_reversal_entry", False)
            and not t.raw_data.get("is_reversed", False)]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pcb_pdf.py <path-to-pdf>")
        sys.exit(1)

    filepath = sys.argv[1]
    print(f"Parsing {filepath}...")
    txns = parse_pcb_pdf(filepath)

    print(f"\nFound {len(txns)} transactions:\n")
    for t in txns:
        flags = []
        if t.raw_data.get("is_reversal"):
            flags.append("REV")
        if t.raw_data.get("is_reversal_entry"):
            flags.append("SKIP")
        if t.raw_data.get("is_reversed"):
            flags.append("WAS_REVERSED")
        flag_str = f" [{', '.join(flags)}]" if flags else ""
        print(f"  {t.date} {t.source_account} ${t.amount:>10.2f}  {t.description}{flag_str}")
