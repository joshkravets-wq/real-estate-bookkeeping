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
}

# Note: 2143 N Palethorp St has no main expense ledger sheet (only a
# "Mortgage Expenses" sheet). Excluded from this registry until a proper
# sheet exists or we decide how to handle.


# Manual Overrides Sheet (Bookkeeping Processors folder)
# Per-transaction explicit accounting decisions that take precedence over
# all engine classification logic. Edit in Google Sheets.
MANUAL_OVERRIDES_FILE_ID = "1kkM1nj2DirtnfeuJJJNE4ax1tr6yuRdV-Oy--DC5A8c"
