# Example 1 — Ingredient Check

**Product loaded:** LMNT Recharge Electrolytes Variety Pack
**URL:** `https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack`

**Prompt:** "Does this have sodium?"

## Tool trace

1. → `check_field(field="ingredients", query="sodium")` → field present; value: `"Sodium (1000mg), Potassium (200mg), Magnesium (60mg)"`; match found at position 0

## Agent response

Yes — LMNT Recharge Electrolytes contains **sodium at 1,000 mg per serving**, which is the dominant electrolyte in the formula.

This is intentionally high. LMNT's formulation philosophy (backed by their published research references) targets the sodium range lost through sweat during moderate-to-intense exercise, which most sports drinks undershoot. The 1,000 mg figure is roughly 43% of the UK Reference Nutrient Intake for sodium per day.

If you are monitoring sodium for dietary or medical reasons, this is worth noting — one stick pack is a meaningful contribution to daily intake.

---
*Tools used: `check_field` · Surface: Streamlit chat*
