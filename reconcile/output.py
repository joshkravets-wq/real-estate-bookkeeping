"""
CSV Writer

Takes a list of classified Transaction objects from the engine and writes
them to a CSV file in the standard format the dashboard expects.

Sections (in order):
  1. Header row
  2. Transaction rows (auto-classified)
  3. Blank row separator
  4. Vendor / 1099 tracker section
  5. Blank row separator
  6. Summary section (P&L, COGS by class, balance sheet)
"""

import csv
from collections import defaultdict
from pathlib import Path


STANDARD_HEADER = [
    "Date", "Month", "Description", "Detail",
    "Amount", "Type", "Check#",
    "QB Account", "Class", "Status",
]

THRESHOLD_1099_NEC = 600.00


def format_date(d):
    return d.strftime("%-d-%b")


def format_month(d):
    return d.strftime("%b").lower()


def format_amount(amount):
    return f"{amount:.2f}"


def format_currency(amount):
    if amount < 0:
        return f"(${abs(amount):,.2f})"
    return f"${amount:,.2f}"


def transaction_to_row(txn):
    return [
        format_date(txn.date),
        format_month(txn.date),
        txn.description,
        f"[{txn.classified_by}]" if txn.classified_by else "",
        format_amount(txn.amount),
        txn.transaction_type or "",
        txn.check_number or "",
        txn.qb_account or "",
        txn.qb_class or "",
        "matched" if not txn.needs_review else "review",
    ]


def extract_payee_from_description(description):
    desc = description.strip()
    if desc.lower().startswith("subcontractor"):
        for sep in [" -- ", " - "]:
            if sep in desc:
                return desc.split(sep, 1)[1].strip()
    if desc.lower().startswith("external withdrawal"):
        rest = desc[len("external withdrawal"):].strip()
        for trailer in [" - SALE", " - PMT", " - ACH", " - AUTOPAYBUS"]:
            if trailer in rest.upper():
                idx = rest.upper().index(trailer)
                rest = rest[:idx].strip()
                break
        return rest
    return ""


def build_vendor_tracker(transactions, checks_csv=None):
    checks_by_num = {}
    if checks_csv:
        for c in checks_csv:
            checks_by_num[c.check_num] = c

    vendor_data = defaultdict(lambda: defaultdict(float))
    vendor_notes = defaultdict(list)

    for txn in transactions:
        if txn.qb_account != "Subcontractors Expense":
            continue
        payee = ""
        # Priority: txn.payee (from property pass match) > checks_csv > description parse
        if getattr(txn, "payee", None):
            payee = txn.payee
        elif txn.is_check and txn.check_number in checks_by_num:
            payee = checks_by_num[txn.check_number].payee
        else:
            payee = extract_payee_from_description(txn.description)
        if not payee:
            continue
        amount = abs(txn.amount)
        month_key = format_month(txn.date) + "-" + str(txn.date.year % 100)
        vendor_data[payee][month_key] += amount
        vendor_data[payee]["ytd"] += amount
        if txn.qb_class and txn.qb_class not in vendor_notes[payee]:
            vendor_notes[payee].append(txn.qb_class)

    sorted_vendors = sorted(vendor_data.keys())

    rows = []
    rows.append(["", "VENDOR / 1099-NEC TRACKER", "", "", "", "", "", "", "", ""])

    all_months = set()
    for payee in vendor_data:
        for key in vendor_data[payee]:
            if key != "ytd":
                all_months.add(key)
    month_order = ["jan", "feb", "mar", "apr", "may", "jun",
                   "jul", "aug", "sep", "oct", "nov", "dec"]
    sorted_months = sorted(all_months, key=lambda m: month_order.index(m.split("-")[0]))

    vendor_header = ["Vendor Name", "EIN / SSN", "Address", "1099 Type"]
    vendor_header.extend(sorted_months)
    vendor_header.extend(["YTD Total", "Threshold Met?", "Notes"])
    rows.append(vendor_header)

    for payee in sorted_vendors:
        ytd = vendor_data[payee]["ytd"]
        meets = "Yes (>$600)" if ytd >= THRESHOLD_1099_NEC else "No"
        properties_note = ", ".join(vendor_notes[payee]) if vendor_notes[payee] else ""
        notes = f"TBD - need W-9. {properties_note}" if properties_note else "TBD - need W-9"
        row = [payee, "TBD - collect W-9", "TBD - collect W-9", "1099-NEC"]
        for m in sorted_months:
            amt = vendor_data[payee][m]
            row.append(format_currency(amt) if amt > 0 else "")
        row.extend([format_currency(ytd), meets, notes])
        rows.append(row)

    return rows


def build_summary(transactions):
    account_totals = defaultdict(float)
    class_totals = defaultdict(float)
    cogs_accounts = {"Subcontractors Expense", "Construction Costs"}
    income_accounts = set()
    op_ex_accounts = set()
    asset_accounts = set()
    liability_accounts = set()
    bank_accounts = set()

    INCOME_KEYWORDS = ["Income"]
    OP_EX_KEYWORDS = ["Expense", "Service Charges"]
    ASSET_KEYWORDS = ["Due from"]
    LIABILITY_KEYWORDS = ["Chase Ink", "AMEX", "Loan"]
    BANK_KEYWORDS = ["PCB"]

    for txn in transactions:
        if not txn.qb_account:
            continue
        account_totals[txn.qb_account] += txn.amount
        class_totals[(txn.qb_account, txn.qb_class or "")] += txn.amount
        acct = txn.qb_account
        if acct in cogs_accounts:
            pass
        elif any(kw in acct for kw in INCOME_KEYWORDS):
            income_accounts.add(acct)
        elif any(kw in acct for kw in ASSET_KEYWORDS):
            asset_accounts.add(acct)
        elif any(kw in acct for kw in BANK_KEYWORDS):
            bank_accounts.add(acct)
        elif any(kw in acct for kw in LIABILITY_KEYWORDS):
            liability_accounts.add(acct)
        elif any(kw in acct for kw in OP_EX_KEYWORDS):
            op_ex_accounts.add(acct)

    rows = []
    rows.append(["", "SUMMARY", "", "", "", "", "", "", "", ""])
    rows.append([])
    rows.append(["", "P&L SUMMARY", "", "", "", "", "", "", "", ""])

    total_income = sum(account_totals[a] for a in income_accounts)
    total_cogs = -sum(account_totals[a] for a in cogs_accounts if a in account_totals)
    total_op_ex = -sum(account_totals[a] for a in op_ex_accounts)
    net_income = total_income - total_cogs - total_op_ex

    if income_accounts:
        for acct in sorted(income_accounts):
            rows.append(["", "", f"  {acct}", "", format_amount(account_totals[acct]), "", "", "", "", ""])
        rows.append(["", "", "Total Income", "", format_amount(total_income), "", "", "", "", ""])
        rows.append([])

    if any(a in account_totals for a in cogs_accounts):
        rows.append(["", "", "COGS", "", "", "", "", "", "", ""])
        for acct in sorted(cogs_accounts):
            if acct in account_totals:
                rows.append(["", "", f"  {acct}", "", format_amount(-account_totals[acct]), "", "", "", "", ""])
        rows.append(["", "", "Total COGS", "", format_amount(total_cogs), "", "", "", "", ""])
        rows.append([])

    if op_ex_accounts:
        rows.append(["", "", "Operating Expenses", "", "", "", "", "", "", ""])
        for acct in sorted(op_ex_accounts):
            rows.append(["", "", f"  {acct}", "", format_amount(-account_totals[acct]), "", "", "", "", ""])
        rows.append(["", "", "Total Op Ex", "", format_amount(total_op_ex), "", "", "", "", ""])
        rows.append([])

    rows.append(["", "", "NET INCOME (LOSS)", "", format_amount(net_income), "", "", "", "", ""])
    rows.append([])

    cogs_by_class = defaultdict(lambda: defaultdict(float))
    for (acct, klass), amt in class_totals.items():
        if acct in cogs_accounts and klass:
            cogs_by_class[klass][acct] = -amt

    if cogs_by_class:
        rows.append(["", "COGS BY CLASS", "", "", "", "", "", "", "", ""])
        for klass in sorted(cogs_by_class.keys()):
            class_total = sum(cogs_by_class[klass].values())
            rows.append(["", "", klass, "", format_amount(class_total), "", "", "", "", klass])
            for acct in sorted(cogs_by_class[klass]):
                rows.append(["", "", f"    {acct}", "", format_amount(cogs_by_class[klass][acct]), "", "", "", "", klass])
        rows.append([])

    if asset_accounts or liability_accounts or bank_accounts:
        rows.append(["", "BALANCE SHEET IMPACTS", "", "", "", "", "", "", "", ""])
        if bank_accounts:
            rows.append(["", "", "Bank account net activity", "", "", "", "", "", "", ""])
            for acct in sorted(bank_accounts):
                rows.append(["", "", f"  {acct}", "", format_amount(account_totals[acct]), "", "", "", "", ""])
        for acct in sorted(asset_accounts):
            rows.append(["", "", f"  {acct} (asset)", "", format_amount(account_totals[acct]), "", "", "", "", ""])
        for acct in sorted(liability_accounts):
            rows.append(["", "", f"  {acct} (liability)", "", format_amount(account_totals[acct]), "", "", "", "", ""])

    return rows


def write_csv(transactions, output_path, vendor_rows=None, summary_rows=None):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(STANDARD_HEADER)
        for txn in transactions:
            writer.writerow(transaction_to_row(txn))
        if vendor_rows:
            writer.writerow([])
            for row in vendor_rows:
                writer.writerow(row)
        if summary_rows:
            writer.writerow([])
            for row in summary_rows:
                writer.writerow(row)
    return str(output_path)


def filename_for(entity_name, period):
    return f"{entity_name} - {period} - Processor.csv"


def write_engine_output(classified_transactions, review_items, entity_name, period,
                        output_dir="./output", checks_csv=None):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_filename = filename_for(entity_name, period)
    csv_path = output_dir / csv_filename
    vendor_rows = build_vendor_tracker(classified_transactions, checks_csv=checks_csv)
    summary_rows = build_summary(classified_transactions)
    write_csv(classified_transactions, str(csv_path),
              vendor_rows=vendor_rows, summary_rows=summary_rows)
    paths = {"csv": str(csv_path)}
    if review_items:
        review_filename = f"{entity_name} - {period} - Review.txt"
        review_path = output_dir / review_filename
        with open(review_path, "w", encoding="utf-8") as f:
            f.write(f"REVIEW ITEMS for {entity_name} - {period}\n")
            f.write("=" * 70 + "\n\n")
            f.write(f"The engine could not auto-classify the following {len(review_items)} ")
            f.write("transactions. Resolve each, then re-run.\n\n")
            for i, item in enumerate(review_items, 1):
                f.write(f"[{i}] {item.transaction.date} {item.transaction.source_account} ")
                f.write(f"${item.transaction.amount:>10.2f}\n")
                f.write(f"    Description: {item.transaction.description}\n")
                f.write(f"    Reason: {item.reason}\n")
                if item.suggested_account:
                    f.write(f"    Suggested account: {item.suggested_account}\n")
                if item.suggested_class:
                    f.write(f"    Suggested class: {item.suggested_class}\n")
                f.write("\n")
        paths["review"] = str(review_path)
    return paths
