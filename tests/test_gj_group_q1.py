"""
Validation test -- runs the engine on G&J Group Q1 2026 mock data
and verifies it produces the same classifications we approved manually.

This is the "does the engine actually work" test. If this passes,
the engine logic is sound and we can wire up real PDF parsers next.
"""

import sys
import os
from datetime import date

# Allow running from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from reconcile.engine import (
    Transaction, CheckRecord, ExpenseSheetEntry, reconcile,
)
from rules import gj_group


def make_q1_2026_bank_transactions():
    """Hardcoded list of all G&J Group Q1 2026 bank transactions, matching
    what we manually classified. NSF reversals excluded since they net to zero."""
    return [
        # PCB 5494 January
        Transaction("PCB 5494", date(2026, 1, 2), "Check 182", -3000.00),
        Transaction("PCB 5494", date(2026, 1, 5), "External Withdrawal MCM LTD, INC - SALE", -220.00),
        Transaction("PCB 5494", date(2026, 1, 5), "External Withdrawal MCM LTD, INC - SALE", -2835.00),
        Transaction("PCB 5494", date(2026, 1, 6), "Deposit Transfer between Gj accounts", 5000.00),
        Transaction("PCB 5494", date(2026, 1, 6), "Check 183", -1485.00),
        Transaction("PCB 5494", date(2026, 1, 12), "Deposit Gj holding to gj. 5494", 10000.00),
        Transaction("PCB 5494", date(2026, 1, 12), "Check 184", -1800.00),
        Transaction("PCB 5494", date(2026, 1, 15), "Deposit Gj holdings to GJ 5494", 5000.00),
        Transaction("PCB 5494", date(2026, 1, 16), "Check 185", -1270.00),
        Transaction("PCB 5494", date(2026, 1, 20), "External Withdrawal CHASE CREDIT CRD - AUTOPAYBUS", -10451.40),
        Transaction("PCB 5494", date(2026, 1, 20), "Deposit Contractor payment GJ hold to 5494", 5000.00),
        Transaction("PCB 5494", date(2026, 1, 21), "Check 186", -3000.00),
        Transaction("PCB 5494", date(2026, 1, 21), "Check 187", -3225.00),
        # PCB 5494 February
        Transaction("PCB 5494", date(2026, 2, 2), "Deposit Contractor payment from GJ Holding", 5000.00),
        Transaction("PCB 5494", date(2026, 2, 3), "Check 141", -5500.00),
        Transaction("PCB 5494", date(2026, 2, 6), "Check 188", -3050.00),
        Transaction("PCB 5494", date(2026, 2, 9), "Deposit Transfer 5501 to 5494", 1500.00),
        Transaction("PCB 5494", date(2026, 2, 18), "Check 189", -420.00),
        Transaction("PCB 5494", date(2026, 2, 19), "Deposit Contractor payment from GJ Holdings", 35000.00),
        Transaction("PCB 5494", date(2026, 2, 19), "External Withdrawal CHASE CREDIT CRD - AUTOPAYBUS", -29346.14),
        Transaction("PCB 5494", date(2026, 2, 26), "Withdrawal Transfer btw GJ groups", -2000.00),
        # PCB 5494 March
        Transaction("PCB 5494", date(2026, 3, 9), "Deposit Reimbursement for 2139 N 7th St Insurance Payment", 1973.00),
        Transaction("PCB 5494", date(2026, 3, 20), "Deposit Internet Transfer from 9000856207 CK", 5000.00),
        Transaction("PCB 5494", date(2026, 3, 20), "Deposit need to cover credit card bill", 8000.00,
                    raw_data={"manual_note": "From GJ Holdings per Josh"}),
        Transaction("PCB 5494", date(2026, 3, 20), "External Withdrawal CHASE CREDIT CRD - AUTOPAYBUS", -18517.33),
        Transaction("PCB 5494", date(2026, 3, 24), "Check 191", -360.00),
        # PCB 5501
        Transaction("PCB 5501", date(2026, 1, 6), "Withdrawal Transfer between Gj accounts", -5000.00),
        Transaction("PCB 5501", date(2026, 1, 26), "External Withdrawal AMEX EPAYMENT AM - ACH PMT A9852", -4229.98),
        Transaction("PCB 5501", date(2026, 1, 28), "Deposit Contractor payment from 10thF", 2000.00),
        Transaction("PCB 5501", date(2026, 1, 28), "Deposit Contractor payment from 10F", 1500.00),
        Transaction("PCB 5501", date(2026, 2, 2), "External Withdrawal AMEX EPAYMENT AM - ACH PMT A4778", -19.98),
        Transaction("PCB 5501", date(2026, 2, 9), "Withdrawal Transfer 5501 to 5494", -1500.00),
        Transaction("PCB 5501", date(2026, 2, 23), "Insufficient Funds Charge External Withdrawal AMEX EPAYMENT", -35.00,
                    raw_data={"is_reversed": False}),
        Transaction("PCB 5501", date(2026, 2, 26), "External Withdrawal AMEX EPAYMENT AM (R) - RETRY PYMT A1822", -2884.90),
        Transaction("PCB 5501", date(2026, 2, 26), "Deposit Transfer btw GJ groups", 2000.00),
        Transaction("PCB 5501", date(2026, 3, 25), "Deposit Contractor payment", 5000.00,
                    raw_data={"manual_note": "From GJ Holdings per Josh"}),
        Transaction("PCB 5501", date(2026, 3, 25), "External Withdrawal AMEX EPAYMENT AM - ACH PMT A5076", -2740.44),
        Transaction("PCB 5501", date(2026, 3, 31), "External Withdrawal AMEX EPAYMENT AM - ACH PMT A1904", -29.97),
    ]


def make_q1_2026_checks_csv():
    """Mock the Checks CSV that Claude would have produced from the bank statement
    PDFs (with check images)."""
    return [
        CheckRecord("PCB 5494", "182", date(2026, 1, 2), 3000.00, "Freeway Contractors Corp",
                    "Elkhart Deposit Drywall", "Subcontractors Expense", "2563 E Elkhart St"),
        CheckRecord("PCB 5494", "183", date(2026, 1, 6), 1485.00, "Edco Insulation",
                    "5461 W Berks St Insulation", "Subcontractors Expense", "5461 W Berks St"),
        CheckRecord("PCB 5494", "184", date(2026, 1, 12), 1800.00, "Freeway Contractors Corp",
                    "Elkhart Balance + Trash Drywall", "Subcontractors Expense", "2563 E Elkhart St"),
        CheckRecord("PCB 5494", "185", date(2026, 1, 16), 1270.00, "MSC LTD",
                    "Elkhart Kitchen + Bath", "Subcontractors Expense", "2563 E Elkhart St"),
        CheckRecord("PCB 5494", "186", date(2026, 1, 21), 3000.00, "Freeway Contractors Corp",
                    "Deposit Grays Ave Drywall", "Subcontractors Expense", "5746 Grays Ave"),
        CheckRecord("PCB 5494", "187", date(2026, 1, 21), 3225.00, "MSC LTD",
                    "Balance 5461 W Berks Kitchen + Vanity", "Subcontractors Expense", "5461 W Berks St"),
        CheckRecord("PCB 5494", "141", date(2026, 2, 3), 5500.00, "Bel Fiberglass Decking",
                    "5746 Grays Ave Roofing", "Subcontractors Expense", "5746 Grays Ave"),
        CheckRecord("PCB 5494", "188", date(2026, 2, 6), 3050.00, "Freeway Contractors Corp",
                    "Final payment Grays Ave", "Subcontractors Expense", "5746 Grays Ave"),
        CheckRecord("PCB 5494", "189", date(2026, 2, 18), 420.00, "Star Builder Inc",
                    "Elkhart", "Subcontractors Expense", "2563 E Elkhart St"),
        CheckRecord("PCB 5494", "191", date(2026, 3, 24), 360.00, "Star Builder Inc",
                    "2563 Elkhart", "Subcontractors Expense", "2563 E Elkhart St"),
    ]


def expected_classifications():
    """The classifications we approved manually for G&J Group Q1 2026."""
    return [
        # (date, source_account, amount, expected_qb_account, expected_class)
        (date(2026, 1, 2), "PCB 5494", -3000.00, "Subcontractors Expense", "2563 E Elkhart St"),
        (date(2026, 1, 6), "PCB 5494", -1485.00, "Subcontractors Expense", "5461 W Berks St"),
        (date(2026, 1, 12), "PCB 5494", -1800.00, "Subcontractors Expense", "2563 E Elkhart St"),
        (date(2026, 1, 16), "PCB 5494", -1270.00, "Subcontractors Expense", "2563 E Elkhart St"),
        (date(2026, 1, 21), "PCB 5494", -3000.00, "Subcontractors Expense", "5746 Grays Ave"),
        (date(2026, 1, 21), "PCB 5494", -3225.00, "Subcontractors Expense", "5461 W Berks St"),
        (date(2026, 2, 3), "PCB 5494", -5500.00, "Subcontractors Expense", "5746 Grays Ave"),
        (date(2026, 2, 6), "PCB 5494", -3050.00, "Subcontractors Expense", "5746 Grays Ave"),
        (date(2026, 2, 18), "PCB 5494", -420.00, "Subcontractors Expense", "2563 E Elkhart St"),
        (date(2026, 3, 24), "PCB 5494", -360.00, "Subcontractors Expense", "2563 E Elkhart St"),
        # Income
        (date(2026, 1, 12), "PCB 5494", 10000.00, "Construction Income", None),
        (date(2026, 1, 15), "PCB 5494", 5000.00, "Construction Income", None),
        (date(2026, 1, 20), "PCB 5494", 5000.00, "Construction Income", None),
        (date(2026, 2, 2), "PCB 5494", 5000.00, "Construction Income", None),
        (date(2026, 2, 19), "PCB 5494", 35000.00, "Construction Income", None),
        (date(2026, 1, 28), "PCB 5501", 2000.00, "Construction Income", None),
        (date(2026, 1, 28), "PCB 5501", 1500.00, "Construction Income", None),
        # Reimbursement
        (date(2026, 3, 9), "PCB 5494", 1973.00, "Due from Sophia Holdings", None),
        # Bank fee
        (date(2026, 2, 23), "PCB 5501", -35.00, "Bank Service Charges", None),
        # CC payments
        (date(2026, 1, 20), "PCB 5494", -10451.40, "Chase Ink 3600", None),
        (date(2026, 2, 19), "PCB 5494", -29346.14, "Chase Ink 3600", None),
        (date(2026, 3, 20), "PCB 5494", -18517.33, "Chase Ink 3600", None),
        (date(2026, 1, 26), "PCB 5501", -4229.98, "AMEX", None),
        (date(2026, 2, 2), "PCB 5501", -19.98, "AMEX", None),
        (date(2026, 2, 26), "PCB 5501", -2884.90, "AMEX", None),
        (date(2026, 3, 25), "PCB 5501", -2740.44, "AMEX", None),
        (date(2026, 3, 31), "PCB 5501", -29.97, "AMEX", None),
    ]


def run_validation():
    bank_txns = make_q1_2026_bank_transactions()
    checks = make_q1_2026_checks_csv()

    classified, reviews = reconcile(
        bank_transactions=bank_txns,
        card_transactions=[],
        checks=checks,
        expense_sheets={},
        rules_module=gj_group,
    )

    expected = expected_classifications()
    print(f"\n{'='*70}")
    print(f"G&J Group Q1 2026 -- Engine Validation")
    print(f"{'='*70}\n")
    print(f"Total bank transactions: {len(bank_txns)}")
    print(f"Auto-classified: {len(classified)}")
    print(f"Need review: {len(reviews)}")
    print(f"Expected classifications: {len(expected)}\n")

    matches = 0
    misses = []
    for exp in expected:
        exp_date, exp_acct, exp_amt, exp_qb_acct, exp_class = exp
        found = False
        for txn in classified:
            if (txn.date == exp_date
                and txn.source_account == exp_acct
                and abs(txn.amount - exp_amt) < 0.01):
                if txn.qb_account == exp_qb_acct and txn.qb_class == exp_class:
                    matches += 1
                    found = True
                else:
                    misses.append(
                        f"  X {exp_date} {exp_acct} ${exp_amt:>10.2f}: "
                        f"got ({txn.qb_account!r}, {txn.qb_class!r}), "
                        f"expected ({exp_qb_acct!r}, {exp_class!r}) "
                        f"[rule: {txn.classified_by}]"
                    )
                    found = True
                break
        if not found:
            misses.append(
                f"  ? {exp_date} {exp_acct} ${exp_amt:>10.2f}: "
                f"NOT FOUND in classified output (expected {exp_qb_acct}, {exp_class})"
            )

    print(f"Matches: {matches}/{len(expected)}\n")
    if misses:
        print("Misses:")
        for m in misses:
            print(m)

    if reviews:
        print(f"\nItems flagged for review (these are EXPECTED to need user input):")
        for r in reviews:
            print(f"  - {r.transaction.date} {r.transaction.source_account} "
                  f"${r.transaction.amount:>10.2f} '{r.transaction.description[:50]}': "
                  f"{r.reason}")

    print(f"\n{'='*70}")
    if matches == len(expected) and not misses:
        print("PASS -- engine reproduces approved Q1 2026 classifications")
    else:
        print(f"INCOMPLETE -- {matches}/{len(expected)} matched, {len(misses)} misses")
    print(f"{'='*70}\n")

    return matches == len(expected) and not misses


if __name__ == "__main__":
    run_validation()
