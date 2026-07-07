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

# Optional dependency - vendor aliases are loaded lazily if available
try:
    from reconcile.loaders.vendor_aliases import load_aliases, canonicalize
    from rules.properties_registry import VENDOR_ALIASES_FILE_ID
    _VENDOR_ALIASES_AVAILABLE = True
except (ImportError, Exception):
    _VENDOR_ALIASES_AVAILABLE = False


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


def build_vendor_tracker(transactions, checks_csv=None, vendor_aliases=None, retail_patterns=None):
    """Build the vendor / 1099-NEC tracker section.
    
    If vendor_aliases is provided (dict from load_aliases()), payees are
    canonicalized before bucketing.
    """
    checks_by_num = {}
    if checks_csv:
        for c in checks_csv:
            checks_by_num[c.check_num] = c

    # Lazy-load aliases if not passed
    if vendor_aliases is None and _VENDOR_ALIASES_AVAILABLE:
        try:
            vendor_aliases = load_aliases(VENDOR_ALIASES_FILE_ID)
        except Exception as e:
            print(f"  WARNING: Could not load vendor aliases: {e}")
            vendor_aliases = {}
    if vendor_aliases is None:
        vendor_aliases = {}

    vendor_data = defaultdict(lambda: defaultdict(float))
    vendor_notes = defaultdict(list)
    vendor_meta = {}  # canonical name -> dict with ein, address

    retail_patterns_lower = [pat.lower() for pat in (retail_patterns or [])]

    def _is_retail(payee_str):
        if not payee_str:
            return False
        pl = payee_str.lower()
        return any(pat in pl for pat in retail_patterns_lower)

    VENDOR_TRACKED_ACCOUNTS = {"Subcontractors Expense", "Construction Costs", "Management Fees"}

    def _looks_like_property(name):
        """Detect if qb_account name looks like a property address (e.g., '5461 W Berks St')."""
        if not name:
            return False
        # Property names start with digits and have a street suffix or directional indicator
        import re
        return bool(re.match(r"^\d+\s+[NSEW]?\s*\w+", name))

    for txn in transactions:
        # Track txns in COGS accounts OR pre-stab property capitalized payments
        # (Asset type + qb_account looks like a property address)
        in_cogs = txn.qb_account in VENDOR_TRACKED_ACCOUNTS
        in_pre_stab_capture = (
            getattr(txn, "transaction_type", "") == "Asset"
            and _looks_like_property(txn.qb_account)
        )
        if not (in_cogs or in_pre_stab_capture):
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
                # Fallback: use description directly for Chase txns
                # (most Chase descriptions ARE the vendor name, e.g., "ANGEL HEATING AND COOLIN")
                payee = txn.description.strip()
        if not payee:
            continue
        # Skip bank-description fallbacks: these aren't real vendor names.
        # Common when Manual Override items don't have payee/check info.
        payee_lower = payee.strip().lower()
        BANK_FALLBACK_PREFIXES = (
            "check", "deposit", "withdrawal",
            "electronic deposit", "external withdrawal",
            "external deposit", "mobile deposit",
        )
        if any(payee_lower.startswith(p) for p in BANK_FALLBACK_PREFIXES):
            continue
        if _is_retail(payee):
            continue
        # Canonicalize payee using alias registry (if loaded)
        alias = canonicalize(payee, vendor_aliases) if vendor_aliases else None
        if alias:
            payee = alias.canonical_name
            if payee not in vendor_meta:
                vendor_meta[payee] = {
                    "ein": alias.ein_ssn,
                    "address": alias.address,
                }
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
        meta = vendor_meta.get(payee, {})
        ein_display = meta.get("ein") or "TBD - collect W-9"
        addr_display = meta.get("address") or "TBD - collect W-9"
        row = [payee, ein_display, addr_display, "1099-NEC"]
        for m in sorted_months:
            amt = vendor_data[payee][m]
            row.append(format_currency(amt) if amt > 0 else "")
        row.extend([format_currency(ytd), meets, notes])
        rows.append(row)

    return rows


def build_summary(transactions, loan_ending_balances=None):
    """Build the reconciliation summary section appended to the Processor CSV.

    Auto-detects entity shape from transaction data:
      - Pre-stab property capitalization (property name as qb_account)
      - Stabilized property P&L (property name as qb_class)
      - Equity activity (member capital accounts)
      - Intercompany (Due from / Due to accounts)
      - Loans, banks, COGS
      - Major events (Gain on Sale, large txns > $100K)
    """
    account_totals = defaultdict(float)
    account_counts = defaultdict(int)
    class_totals = defaultdict(float)
    # (qb_account, qb_class) -> [list of (date, amount, description)]
    txn_index = defaultdict(list)

    for txn in transactions:
        if not txn.qb_account:
            continue
        account_totals[txn.qb_account] += txn.amount
        account_counts[txn.qb_account] += 1
        klass = txn.qb_class or ""
        class_totals[(txn.qb_account, klass)] += txn.amount
        txn_index[txn.qb_account].append((txn.date, txn.amount, txn.description))

    # ---- Categorize accounts ----
    income_accounts = set()
    expense_accounts = set()
    cogs_accounts = {"Subcontractors Expense", "Construction Costs"}
    asset_accounts = set()              # "Due from X" intercompany
    pre_stab_property_accts = set()     # Property name as qb_account
    liability_accounts = set()
    bank_accounts = set()
    equity_accounts = set()
    gain_on_sale_accounts = set()
    other_accounts = set()

    INCOME_KW = ["Income", "Rental Income"]
    EXPENSE_KW = ["Expense", "Service Charges", "Taxes -", "Water", "Insurance",
                  "Gas Expense", "PECO Expense", "Professional Fees",
                  "Management Fees", "Licenses & Permits"]
    LIABILITY_KW = ["Loan", "Chase Ink", "AMEX", "Construction Loan"]
    BANK_KW = ["PCB", "TD ", "Penn Community"]
    EQUITY_KW = ["Capital:", "Capital ", "Contribution", "Draw", "Equity"]
    INTERCO_KW = ["Due from", "Due to"]
    GAIN_KW = ["Gain on Sale", "Loss on Sale"]

    # Property name detection: account names that look like addresses
    # Heuristic: contains a number followed by a space and an uppercase word
    import re
    PROPERTY_NAME_REGEX = re.compile(r"^\d+[A-Z]?\s+[A-Z]")

    for acct in account_totals.keys():
        if any(kw in acct for kw in GAIN_KW):
            gain_on_sale_accounts.add(acct)
        elif any(kw in acct for kw in EQUITY_KW):
            equity_accounts.add(acct)
        elif any(kw in acct for kw in INTERCO_KW):
            asset_accounts.add(acct)
        elif acct in cogs_accounts:
            pass  # handled separately
        elif PROPERTY_NAME_REGEX.match(acct) or acct.endswith(":Land"):
            pre_stab_property_accts.add(acct)
        elif any(kw in acct for kw in LIABILITY_KW):
            liability_accounts.add(acct)
        elif any(kw in acct for kw in BANK_KW):
            bank_accounts.add(acct)
        elif any(kw in acct for kw in INCOME_KW):
            income_accounts.add(acct)
        elif any(kw in acct for kw in EXPENSE_KW):
            expense_accounts.add(acct)
        else:
            other_accounts.add(acct)

    rows = []
    rows.append(["", "=" * 80, "", "", "", "", "", "", "", ""])
    rows.append(["", "RECONCILIATION SUMMARY", "", "", "", "", "", "", "", ""])
    rows.append(["", "=" * 80, "", "", "", "", "", "", "", ""])
    rows.append([])

    # ---- MAJOR EVENTS ----
    rows.append(["", "MAJOR EVENTS", "", "", "", "", "", "", "", ""])
    has_events = False

    # Sales (Gain on Sale accounts)
    for acct in sorted(gain_on_sale_accounts):
        rows.append(["", "", f"Sale event: {acct}", "",
                     format_amount(account_totals[acct]),
                     f"({account_counts[acct]} txns)", "", "", "", ""])
        has_events = True

    # Large txns (>$100K abs)
    large_txns = []
    for acct, txns in txn_index.items():
        for d, amt, desc in txns:
            if abs(amt) >= 100000:
                large_txns.append((d, amt, acct, desc))
    if large_txns:
        rows.append(["", "", "Large transactions (≥$100,000):", "", "", "", "", "", "", ""])
        for d, amt, acct, desc in sorted(large_txns):
            d_str = d.isoformat() if hasattr(d, "isoformat") else str(d)
            rows.append(["", "", f"  {d_str}", "",
                         format_amount(amt),
                         f"{acct}", "", "", "", ""])
        has_events = True

    if not has_events:
        rows.append(["", "", "(none)", "", "", "", "", "", "", ""])
    rows.append([])

    # ---- P&L BY PROPERTY (stabilized only) ----
    pl_by_class = defaultdict(lambda: {"income": 0.0, "expense": 0.0})
    for (acct, klass), amt in class_totals.items():
        if not klass:
            continue
        if acct in income_accounts:
            pl_by_class[klass]["income"] += amt
        elif acct in expense_accounts or acct in cogs_accounts:
            pl_by_class[klass]["expense"] += amt

    if pl_by_class:
        rows.append(["", "P&L BY PROPERTY (stabilized)", "", "", "", "", "", "", "", ""])
        for klass in sorted(pl_by_class.keys()):
            pl = pl_by_class[klass]
            net = pl["income"] + pl["expense"]
            rows.append(["", "", klass, "", "", "", "", "", "", klass])
            # Itemize income accounts for this property
            rows.append(["", "", "  Income", "", format_amount(pl["income"]), "", "", "", "", klass])
            for (acct, kls), amt in sorted(class_totals.items(), key=lambda x: -abs(x[1])):
                if kls == klass and acct in income_accounts and amt != 0:
                    rows.append(["", "", f"    {acct}", "", format_amount(amt), "", "", "", "", klass])
            # Itemize expense accounts for this property
            rows.append(["", "", "  Expenses", "", format_amount(pl["expense"]), "", "", "", "", klass])
            for (acct, kls), amt in sorted(class_totals.items(), key=lambda x: -abs(x[1])):
                if kls == klass and (acct in expense_accounts or acct in cogs_accounts) and amt != 0:
                    rows.append(["", "", f"    {acct}", "", format_amount(amt), "", "", "", "", klass])
            rows.append(["", "", "  Net P&L", "", format_amount(net), "", "", "", "", klass])
        rows.append([])

    # ---- ASSET CAPITALIZATION (pre-stab properties) ----
    if pre_stab_property_accts:
        rows.append(["", "ASSET CAPITALIZATION (pre-stab properties)", "", "", "", "", "", "", "", ""])
        total_capitalized = 0.0
        for acct in sorted(pre_stab_property_accts):
            amt = account_totals[acct]
            total_capitalized += amt
            rows.append(["", "", acct, "",
                         format_amount(amt),
                         f"({account_counts[acct]} txns)", "", "", "", ""])
        rows.append(["", "", "Total asset additions/clearings", "",
                     format_amount(total_capitalized), "", "", "", "", ""])
        rows.append([])

    # ---- LIABILITIES ----
    if liability_accounts:
        rows.append(["", "LIABILITY CHANGES", "", "", "", "", "", "", "", ""])
        for acct in sorted(liability_accounts):
            _bal_note = ""
            if loan_ending_balances:
                for _ln, _bal in loan_ending_balances.items():
                    if _ln in acct:
                        _bal_note = f"ending balance per servicer: {format_amount(_bal)}"
                        break
            rows.append(["", "", acct, "",
                         format_amount(account_totals[acct]),
                         f"({account_counts[acct]} txns)", _bal_note, "", "", ""])
        rows.append([])

    # ---- INTERCOMPANY ----
    if asset_accounts:
        rows.append(["", "INTERCOMPANY (Due from / Due to)", "", "", "", "", "", "", "", ""])
        for acct in sorted(asset_accounts):
            rows.append(["", "", acct, "",
                         format_amount(account_totals[acct]),
                         f"({account_counts[acct]} txns)", "", "", "", ""])
        rows.append([])

    # ---- EQUITY ACTIVITY ----
    if equity_accounts:
        rows.append(["", "EQUITY ACTIVITY", "", "", "", "", "", "", "", ""])
        contribs = sum(account_totals[a] for a in equity_accounts if account_totals[a] > 0)
        draws = sum(account_totals[a] for a in equity_accounts if account_totals[a] < 0)
        for acct in sorted(equity_accounts):
            rows.append(["", "", acct, "",
                         format_amount(account_totals[acct]),
                         f"({account_counts[acct]} txns)", "", "", "", ""])
        rows.append(["", "", "Total contributions", "", format_amount(contribs), "", "", "", "", ""])
        rows.append(["", "", "Total distributions", "", format_amount(draws), "", "", "", "", ""])
        rows.append(["", "", "Net equity change", "", format_amount(contribs + draws), "", "", "", "", ""])
        rows.append([])

    # ---- TOP-LEVEL P&L ROLLUP ----
    total_income = sum(account_totals[a] for a in income_accounts) + sum(account_totals[a] for a in gain_on_sale_accounts)
    total_expense = sum(account_totals[a] for a in expense_accounts)
    total_cogs = sum(account_totals[a] for a in cogs_accounts if a in account_totals)
    net_pl = total_income + total_expense + total_cogs

    rows.append(["", "OVERALL P&L (this period)", "", "", "", "", "", "", "", ""])
    rows.append(["", "", "Total income (incl. gains)", "", format_amount(total_income), "", "", "", "", ""])
    if total_cogs != 0:
        rows.append(["", "", "Total COGS", "", format_amount(total_cogs), "", "", "", "", ""])
    rows.append(["", "", "Total expenses", "", format_amount(total_expense), "", "", "", "", ""])
    rows.append(["", "", "NET P&L", "", format_amount(net_pl), "", "", "", "", ""])
    rows.append([])

    # ---- ACCOUNT-LEVEL ROLLUP (everything) ----
    rows.append(["", "ACCOUNT-LEVEL ROLLUP", "", "", "", "", "", "", "", ""])
    rows.append(["", "Account", "", "Count", "Net Amount", "", "", "", "", ""])
    for acct in sorted(account_totals.keys(), key=lambda a: -abs(account_totals[a])):
        rows.append(["", "", acct, account_counts[acct],
                     format_amount(account_totals[acct]), "", "", "", "", ""])

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
                        output_dir="./output", checks_csv=None,
                        vendor_tracker_transactions=None, retail_patterns=None,
                        loan_ending_balances=None):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_filename = filename_for(entity_name, period)
    csv_path = output_dir / csv_filename
    vendor_txns = vendor_tracker_transactions if vendor_tracker_transactions is not None else classified_transactions
    vendor_rows = build_vendor_tracker(vendor_txns, checks_csv=checks_csv, retail_patterns=retail_patterns)
    summary_rows = build_summary(classified_transactions, loan_ending_balances=loan_ending_balances)
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
