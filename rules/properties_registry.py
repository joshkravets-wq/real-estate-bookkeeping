"""
Active reno property registry.

Minimal map of property name -> Drive file ID for expense sheets.
Used by the property expense sheet matching pass in run_reconcile.py.

Rich property metadata (status, entity, pre-stab vs stabilized) lives
in rules/properties.py. This file is intentionally narrow - just the
file_id mapping the engine needs to fetch sheets.
"""

# Active reno properties (Tier 1 search per CHASE CARD METHODOLOGY)
ACTIVE_RENO_FILE_IDS = {
    "5461 W Berks St":    "1tp1IX4hqlmPXKhYGDkuKa91rCNx5xklyoMW6TZpTSbs",
    "5746 Grays Ave":     "1kKNKkzX9zJTKjCkx4DYHoJ1ZSZs97pWQNps3xTmG99U",
    "2563 E Elkhart St":  "1V_1L2cAwlahesTmMe_JVudb31ssixzQ_5rE-rpAsjSA",
    "2925 Master St":     "1ojuSpDw1TzHuA9uxnkZN3uUpE_QJMXDAdZtCj_ojrYA",
    "2030 N Lawrence St": "1m_LrYHJFxp8eDXJXZPsbK3FKKA1WwlfJCSE-BveSEfU",
    "2139 N 7th St":      "1vlCXXcTl_NzpCCy5aNTeEA5ldqIncDKoR25pH1p_mLM",
    "2672 Braddock Ave":  "1C7HjOzD76WAkSYb47DI7AfBxtHyAEeak9wNS3TSIGOw",
    "2433 N 6th St":      "1aSa3NnrLyIYvR8Tv-uboboFFfUPWUhomOWMsYU1LdHY",
    "7338 N 20th St":     "1r_NZDbk4phpUN-WONZPBniraJQrq34JmAfCvx6zYfNY",
    "2428 N Fairhill St": "1xUn7F3HOTuf2L8QlCrq-8f6tdN5KicO96fvJvzr77KE",
    "6541 Edmund St":     "13MHbVjDIvgH9nzImVZWO4hK20f-I1n8drYg5fTNu3pc",
    # Stabilized rentals — Chase card also covers rental maintenance (Jul 2026)
    "314 W Norris St":    "1qW72_3toUAXdN1d3slcXPjdETXVq5nIk_TKuXMjT4S0",
    "1948 N Orianna St":  "1R4PMsDDQq-ChS-B_yp20_5sJO6lYOg3zKM8S5ixHYkI",
    "507 W Dauphin St":   "1j-o-S52019bDhUOUG5NVY5WnsXGkbquUIZ3iWyEWbus",
    "1934 N 3rd St":      "1LhECwr8rLI8TazvHVUzCfd_IYSeugK8fnCBm3Ksxy54",
    "438 W Susquehanna Ave": "17Vj8a1bAB5ECoAtrhyMGLnp7yn2IRr8LvnYKMXFqIME",
    "2143 N Palethorp St": "1jhMJ99CUEGt9_kjZLBs8FUZGQMl0aRDZxrU4J-UuHyk",
}

# Note: 2143 N Palethorp St has no main expense ledger sheet (only a
# "Mortgage Expenses" sheet). Excluded from this registry until a proper
# sheet exists or we decide how to handle.


# Manual Overrides Sheet (Bookkeeping Processors folder)
# Per-transaction explicit accounting decisions that take precedence over
# all engine classification logic. Edit in Google Sheets.
MANUAL_OVERRIDES_FILE_ID = "1kkM1nj2DirtnfeuJJJNE4ax1tr6yuRdV-Oy--DC5A8c"


# Vendor Aliases Sheet (Bookkeeping Processors folder)
# Maps spelling variants (as they appear in property expense sheets and
# bank statement descriptions) to canonical vendor names. Used by the
# vendor tracker in output.py to consolidate duplicate-spelling rows
# for accurate 1099 threshold tracking.
VENDOR_ALIASES_FILE_ID = "1aRKJyhm8zm5DVXqqQE92zFZ23ajUOVwwF-mgtLxosmo"
