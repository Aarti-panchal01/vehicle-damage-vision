# Role 2 Cost Engine - working update

## Changes in this update
- Preserves the team's Contract B top-level and line-item fields.
- Validates successful Contract A inputs and rejects VisionError objects.
- Handles empty damage lists as a valid zero-cost estimate.
- Groups multiple damage observations by physical part so the same replacement part is not charged once per observation.
- Applies replacement part price only when the selected action is `replace`; repair no longer charges a full replacement part.
- Adds known part-name aliases for the existing price table.
- Treats missing labour, paint, part prices, or depreciation rules as unpriced rather than inventing zero-cost services.
- Adds the five Role 1 Contract A mock reports and tests.

## Run tests
From the project root:
    python -m pytest -q

Latest local result: 69 passed.

## Important data limitations
The current labour_rates.csv and paint_rates.csv contain only their headers. Most parts_prices.csv rows have blank paint_cost_inr. Some part names/year ranges do not match the Role 1 samples, and Honda City/Baleno data is not present. Therefore, the five sample reports are accepted and produce valid Contract B structures, but most damaged parts are correctly listed in `unpriced_parts` until verified data is collected.

No price or labour rate was fabricated. Do not present zero totals for these samples as completed repair estimates.

## Additional hardening (2026-11-09)
- Contract A validation now checks the complete Role 1 required field set, vehicle fuel/year, 26-part enum, confidence and image_index.
- Comparable rates from multiple garages are aggregated using the median; source labels are included in `price_source`.
- Hourly rates are excluded unless a duration is available.
- Added Contract A/B schemas, five sample Contract B-shaped outputs, `sample_audit.json`, `scripts/run_role2_samples.py`, and `data/prices/DATA_QUALITY_AUDIT.md`.
- Added tests for duplicate-damage aggregation, replacement precedence, two-garage median, invalid part names and required Contract A fields.
- Latest test result: 69 passed.

- Added a separate `paint_rates.csv` and paint-rate lookup. All-in painting rates must explicitly include paint material; all-in paint quotes are not double-counted as repair labour.
