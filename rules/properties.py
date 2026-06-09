"""
Property metadata used across all entities.

Each property knows:
  - Which LLC owns it (the entity whose books capitalize/expense costs there)
  - Its status (pre-stab, stabilized, sold, etc.)
  - Drive expense sheet ID (for card transaction matching)
  - Any special handling notes

This file rarely changes. Edit when:
  - A new property is acquired
  - A property's status changes (e.g., construction → stabilized → sold)
  - A property is sold
"""

# Status values:
#   "pre-stab"   = pre-stabilization, all costs capitalized to fixed asset
#   "stabilized" = stabilized rental, costs go to expense accounts + class
#   "sold"       = sold; post-sale costs hit Gain on Sale
#   "vacant"     = vacant lot, capitalize as carrying cost
#   "acquiring"  = in acquisition, costs capitalized

PROPERTIES = {
    # === GJ Holdings LLC ===
    "5461 W Berks St": {
        "llc": "GJ Holdings LLC",
        "status": "pre-stab",
        "expense_sheet_id": "1tp1IX4hqlmPXKhYGDkuKa91rCNx5xklyoMW6TZpTSbs",
        "notes": "Active construction",
    },
    "5746 Grays Ave": {
        "llc": "GJ Holdings LLC",
        "status": "pre-stab",
        "expense_sheet_id": "1kKNKkzX9zJTKjCkx4DYHoJ1ZSZs97pWQNps3xTmG99U",
        "notes": "Active construction",
    },
    "314 W Norris St": {
        "llc": "GJ Holdings LLC",
        "status": "stabilized",
        "expense_sheet_id": None,
        "notes": "Rental duplex; PCB loan 9000798251",
    },
    "1948 N Orianna St": {
        "llc": "GJ Holdings LLC",
        "status": "stabilized",
        "expense_sheet_id": None,
        "notes": "Single family rental; PCB loan 9000829048",
    },
    "507 W Dauphin St": {
        "llc": "GJ Holdings LLC",
        "status": "stabilized",
        "expense_sheet_id": None,
        "notes": "Rental duplex; refi Jan 2026 -> Fay 0000426433",
    },
    "2415 N 4th St": {"llc": "GJ Holdings LLC", "status": "vacant"},
    "2431 N 3rd St": {"llc": "GJ Holdings LLC", "status": "vacant", "notes": "RE tax $587 watch April 2026"},
    "2433 N 6th St": {"llc": "GJ Holdings LLC", "status": "acquiring", "notes": "Glenn Dawson situation"},
    "6541 Edmund St": {"llc": "GJ Holdings LLC", "status": "pre-stab", "notes": "Occupied - eviction pending"},
    "7338 N 20th St": {"llc": "GJ Holdings LLC", "status": "acquiring", "notes": "50% acquired 2/11/2026, second 50% pending"},
    "2428 N Fairhill St": {"llc": "GJ Holdings LLC", "status": "acquiring"},

    # === 10th Fairmount LLC ===
    "1252 N 18th St": {
        "llc": "10th Fairmount LLC",
        "status": "stabilized",
        "expense_sheet_id": None,
        "notes": "Rental duplex; PCB loan 9000854235 4.580%",
    },
    "2925 Master St": {
        "llc": "10th Fairmount LLC",
        "status": "pre-stab",
        "expense_sheet_id": "1ojuSpDw1TzHuA9uxnkZN3uUpE_QJMXDAdZtCj_ojrYA",
        "notes": "Under construction; PCB loan 9001254757 7.750% interest-only",
    },
    "1012 Fairmount Ave": {"llc": "10th Fairmount LLC", "status": "vacant"},
    "1008R Fairmount Ave": {"llc": "10th Fairmount LLC", "status": "vacant"},
    "2030 N Lawrence St": {
        "llc": "10th Fairmount LLC",
        "status": "sold",
        "sold_date": "2026-02-14",
        "expense_sheet_id": "1m_LrYHJFxp8eDXJXZPsbK3FKKA1WwlfJCSE-BveSEfU",
        "notes": "HUD OTA-13518-PA, Gain $89,846. Post-sale costs -> Gain on Sale account.",
    },
    "1008 Fairmount Ave": {"llc": "10th Fairmount LLC", "status": "vacant", "notes": "Co-invested with Veit LLC -> Due from Veit LLC"},
    "1010 Fairmount Ave": {"llc": "10th Fairmount LLC", "status": "vacant", "notes": "Co-invested with Phily Properties -> Due from Phily Properties LLC"},

    # === Cambria Group LLC ===
    "2563 E Elkhart St": {
        "llc": "Cambria Group LLC",
        "status": "pre-stab",
        "expense_sheet_id": "1V_1L2cAwlahesTmMe_JVudb31ssixzQ_5rE-rpAsjSA",
        "notes": "Active construction",
    },

    # === Sophia Holdings LLC ===
    "1934 N 3rd St": {
        "llc": "Sophia Holdings LLC",
        "status": "stabilized",
        "expense_sheet_id": "1LhECwr8rLI8TazvHVUzCfd_IYSeugK8fnCBm3Ksxy54",
        "notes": "Rental duplex. Unit A pays outside RentRedi.",
    },
    "2139 N 7th St": {
        "llc": "Sophia Holdings LLC",
        "status": "stabilized",
        "expense_sheet_id": "1vlCXXcTl_NzpCCy5aNTeEA5ldqIncDKoR25pH1p_mLM",
        "notes": "Rental triplex. Insurance reimbursed by Sophia to G&J Group ($1,973 3/9/26).",
    },
    "438 W Susquehanna Ave": {
        "llc": "Sophia Holdings LLC",
        "status": "stabilized",
        "expense_sheet_id": "17Vj8a1bAB5ECoAtrhyMGLnp7yn2IRr8LvnYKMXFqIME",
        "notes": "Rental duplex.",
    },
    "2143 N Palethorp St": {
        "llc": "Sophia Holdings LLC",
        "status": "stabilized",
        "expense_sheet_id": "1jhMJ99CUEGt9_kjZLBs8FUZGQMl0aRDZxrU4J-UuHyk",
        "notes": "Rental house. 25k mortgage per master inventory.",
    },
    "2148 N 3rd St": {
        "llc": "Sophia Holdings LLC",
        "status": "pre-stab",
        "expense_sheet_id": "1S7kzFulZoF0qK1XijC_TVnXpWxmGOgZ-WUc7S805mGc",
        "notes": "Vacant lot (RM1 14' x 55').",
    },
    "2411 N 3rd St": {
        "llc": "Sophia Holdings LLC",
        "status": "pre-stab",
        "expense_sheet_id": "10Q7HPvvdniYzwbOUq2Zds_wRIgL6-0cpZm55e6_PL2Y",
        "notes": "Vacant lot (RM1 14' x 60').",
    },
    "2024 Wilder St": {
        "llc": "Sophia Holdings LLC",
        "status": "pre-stab",
        "expense_sheet_id": "10p6_ZBq_xQqWwuq2TaaiQfT90tqMbCtTNfQd7jhzB0U",
        "notes": "Vacant lot (RSA5 14'x50').",
    },

    # === Confirm with Josh ===
    "2672 Braddock Ave": {
        "llc": None,
        "status": "pre-stab",
        "expense_sheet_id": None,
        "notes": "Engineer Reserve + L&I permits + city fees recorded against this property in Q1 2026. Confirm owning LLC.",
    },
}


def llc_for_property(property_name):
    """Return the LLC name that owns a given property, or None if unknown."""
    p = PROPERTIES.get(property_name)
    return p["llc"] if p else None


def expense_sheet_id_for(property_name):
    """Return the Drive expense sheet ID for a property, or None."""
    p = PROPERTIES.get(property_name)
    return p.get("expense_sheet_id") if p else None


def is_pre_stab(property_name):
    """True if property is pre-stab (costs capitalize) vs stabilized (costs expense)."""
    p = PROPERTIES.get(property_name)
    return p and p["status"] == "pre-stab"


def all_properties_for_llc(llc_name):
    """Return a list of property names owned by a given LLC."""
    return [name for name, p in PROPERTIES.items() if p.get("llc") == llc_name]
