"""
Vendor Aliases loader.

Reads the Vendor Aliases Google Sheet (in Bookkeeping Processors folder)
and provides a mapping of spelling variants -> canonical vendor name.

Used by the vendor tracker in output.py to consolidate duplicate-spelling
rows. Critical for accurate 1099 threshold tracking, since two rows of
the same vendor at $400 each would not flag the $600 threshold even
though combined they cross it.

Sheet schema:
    Variant Spelling | Canonical Name | EIN/SSN | Address | Notes
"""

from dataclasses import dataclass
from typing import Dict, Optional

from reconcile.drive_client import DriveClient


@dataclass
class VendorAlias:
    variant_spelling: str
    canonical_name: str
    ein_ssn: Optional[str]
    address: Optional[str]
    notes: str


def load_aliases(file_id) -> Dict[str, VendorAlias]:
    """Load vendor aliases from the Drive sheet.
    
    Returns a dict mapping lowercased variant spelling -> VendorAlias.
    Lookups are case-insensitive.
    """
    client = DriveClient()
    wb = client.fetch_spreadsheet(file_id)
    sheet = wb.active

    aliases = {}
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        return aliases

    header = [str(c or "").strip().lower() for c in rows[0]]
    expected = ["variant spelling", "canonical name", "ein/ssn", "address", "notes"]
    for exp in expected:
        if exp not in header:
            raise ValueError(
                f"Vendor Aliases sheet missing expected column '{exp}'. "
                f"Found columns: {header}"
            )

    col = {h: i for i, h in enumerate(header)}

    for row in rows[1:]:
        if all(c is None or c == "" for c in row):
            continue

        try:
            variant = str(row[col["variant spelling"]] or "").strip()
            canonical = str(row[col["canonical name"]] or "").strip()
            ein = str(row[col["ein/ssn"]] or "").strip() or None
            address = str(row[col["address"]] or "").strip() or None
            notes = str(row[col["notes"]] or "").strip()
        except IndexError:
            continue

        if not variant or not canonical:
            continue

        aliases[variant.lower()] = VendorAlias(
            variant_spelling=variant,
            canonical_name=canonical,
            ein_ssn=ein,
            address=address,
            notes=notes,
        )

    return aliases


def canonicalize(payee: str, aliases: Dict[str, VendorAlias]) -> Optional[VendorAlias]:
    """Look up the canonical alias for a payee string."""
    if not payee:
        return None
    return aliases.get(payee.lower().strip())


if __name__ == "__main__":
    from rules.properties_registry import VENDOR_ALIASES_FILE_ID

    print(f"Loading Vendor Aliases from {VENDOR_ALIASES_FILE_ID}...")
    aliases = load_aliases(VENDOR_ALIASES_FILE_ID)
    print(f"Loaded {len(aliases)} aliases")
    print()
    from collections import defaultdict
    by_canonical = defaultdict(list)
    for variant, alias in aliases.items():
        by_canonical[alias.canonical_name].append(alias)
    for canonical, alias_list in sorted(by_canonical.items()):
        variants = sorted(set(a.variant_spelling for a in alias_list))
        print(f"  {canonical}")
        for v in variants:
            print(f"    <- {v!r}")
