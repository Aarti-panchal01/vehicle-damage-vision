# Role 2 — Cost Engine handoff status
Updated: 2026-11-10 (v7)

## Handoff
Role 2 accepts Role 1 Contract A JSON and generates Contract B JSON. See `README.md` for setup and exact run commands.

## Implemented
- Contract A validation, including required fields, enums and the 26-part vocabulary.
- Rejects `VisionError` instead of treating it as a damage report.
- Handles valid no-damage reports with empty line items and zero totals.
- Groups multiple observations of one physical part into one cost line.
- Applies replacement when any observation for that physical part requires replacement.
- Charges a replacement part only for `replace`; repair does not charge a full replacement part.
- Calculates configured material/age-based depreciation and paint depreciation.
- Leaves parts unpriced when required source data is missing instead of fabricating a zero.
- Uses the median when multiple comparable garage rates are supplied for the same model/service.
- Ignores hourly labour rates unless job duration is separately available.
- Validates generated Contract B outputs against the JSON Schema.

## Data included
- `parts_prices.csv`: 48 rows total; Swift 15, Creta 15, Nexon 15, Honda City 2 and Baleno 1.
- `labour_rates.csv` and `paint_rates.csv`: LUSTRO Auto Corp Pvt Ltd quotation data for Swift, Creta and Nexon.
- Range midpoints are used for deterministic calculations; original ranges are retained in source descriptions.
- Garage did not confirm whether painting rates include primer/material. The current `includes_paint_material=yes` setting is provisional and documented in `GARAGE_RATE_DATA_NOTES.md`.
- No second garage quotation was supplied; do not report a second independently collected garage.

## Verification
- Test suite: 71 tests passed in the v7 environment.
- Sample runner: `python scripts/run_role2_samples.py` generates five schema-validated Contract B outputs.
- Swift and Nexon damaged examples are priced; the no-damage example correctly returns zero totals.
- Honda City door sample remains incomplete because the required door replacement labour rates are unavailable.
- Baleno bumper sample remains incomplete because the required painting rate is unavailable.
- A schema-valid Contract B with non-empty `unpriced_parts` is not a complete estimate.

## Pending limitations
1. Obtain and record a second independent garage quotation.
2. Obtain Honda City door replacement labour rates and Baleno painting rates if those sample claims must be fully priced.
3. Verify outstanding part/material classifications and source compatibility flags documented in `MATERIAL_AND_DEPRECIATION_AUDIT.md` and `DATA_QUALITY_AUDIT.md`.
4. Confirm depreciation applicability against the policy applicable to each claim; current values are transcribed from one Shriram policy and are not universal.
5. Confirm with LUSTRO whether painting rates include primer/material and record the exact garage address and GST treatment if available.

## Role 3 integration rule
Consume Contract B as-is. Do not alter its monetary values. If `unpriced_parts` is non-empty, clearly flag the estimate as incomplete and do not present zero totals as a payable claim amount.
