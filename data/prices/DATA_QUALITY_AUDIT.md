# Role 2 pricing-data quality audit
Audit date: 2026-11-09 (updated after v4 integration run)

## Part-price coverage
- Primary engine price table: 36 rows.
- Swift: 15/15 target.
- Creta: 10/15 target (added headlamp listing for 2020-2024; 5 more rows needed).
- Nexon: 10/15 target (5 more rows needed).
- Baleno: one additional front-bumper price row added for the 2015-2022 generation; confirm exact fitment by VIN/variant before treating it as final.
- Honda City 2019: added estimated left front-door and left rear-door base prices from the 4th-generation (2017 onward) ZigWheels listing. Each is ₹6,578 before the page-listed 28% GST (₹8,419 including GST). The v4 integration lookup now finds both prices; labour rates remain missing. These are published estimates, not confirmed VIN-specific dealer quotations; verify trim/fitment before treating as final.
- Paint prices missing: all primary part rows still have blank paint_cost_inr.
- Labour-rate records: 0 (garage quotes pending).
- All-in paint-rate records: 0 (garage quotes pending).

## Newly added source-backed entries
- Hyundai Creta 2020-2024 headlamp (left or right): ₹3,200 listed authorised-dealer price before 28% GST; ₹4,096 including the GST shown by ZigWheels. The primary CSV stores the ₹3,200 base part price. Source: https://www.zigwheels.com/hyundai-cars/creta-2020-2024/spare-parts-price/ (accessed 2026-11-09).
- Maruti Suzuki Baleno front bumper: ₹2,650 catalog MRP for part 71711M68P01-5PK, shown for the 2015-generation Baleno. Primary CSV range is annotated 2015-2022; exact 2020 variant/VIN fitment must be confirmed. Source: https://www.partsinfo.in/catalog/suzuki/baleno/d13a-delta-o-yra-2015-d13a-delta-o/body-bumpers-and-grilles/ (accessed 2026-11-09).

## Research evidence not enabled in engine
- Tata Nexon XZ headlamp listing: ₹10,278 each side in a variant-specific parts catalogue. Sample trim is unknown, so this is retained in research_price_evidence.csv and not used for generic Nexon pricing. Source: https://www.partsinfo.in/catalog/tata/nexon/nexon-xz-54382225r/54-electricals/.
- Honda City front right door listing ₹4,012 is a used part for 2014-2017 and is not suitable for the 2019 sample. A ₹7,281 genuine front-right door listing states Type 7 & 8, but exact 2019 fitment and the opposite/rear door prices are not established. Both are retained as research evidence only, not used in engine calculations.

## Existing evidence notes
- Maruti genuine-parts screenshots are retained in this folder for Swift part rows.
- creta_body_parts_prices.png supports the published Creta list.
- nexon_body_parts_prices.png supports the published Nexon list.
- pitcrew_swift_front_bumper_dent_paint_price.png supports the ₹2,395 inclusive-GST combined dent-repair/full-panel-paint package. Do not split that package into invented labour and paint components.
- The right outside mirror screenshot appears to show ₹715 while the corresponding CSV row says ₹3,470. This conflict is unresolved; keep that row unverified and do not use it for an estimate.
- The Swift right-headlamp row has a compatibility note; parsing the year range does not independently prove exact fitment.

## Sample limitations
- Swift sample: the headlamp part price can now be found, but labour and paint inputs are still missing; front bumper repair labour/paint also remain missing.
- Creta sample: no damage; zero totals are expected.
- Nexon sample: windshield price exists, but replacement labour is missing. Variant-specific headlamp research price is not enabled.
- Honda City sample: both door price lookups now resolve in v4; replacement labour rates remain missing. Confirm VIN/variant fitment before treating published prices as final.
- Baleno sample: front bumper part price is now available provisionally, but repair labour and painting rates remain missing.

## Safe use rule
Only calculate a complete line item when the required part price (for replacement), labour rate, paint rate (when applicable), and depreciation material rule are all available. Keep missing inputs visible; never silently substitute a zero. A non-empty unpriced_parts list means the estimate is incomplete.


## Honda City 2019 sample — added price references (2026-11-09)
- Front left door: ₹6,578 before GST; ₹8,419 including the 28% GST shown on the source page.
- Rear left door: ₹6,578 before GST; ₹8,419 including the 28% GST shown on the source page.
- Source: https://www.zigwheels.com/honda-cars/city-4th-generation/spare-parts-price/ (4th-generation Honda City; listing labels front/rear door left or right).
- The CSV stores the listed base amount ₹6,578, not the GST-inclusive amount, to keep the same pre-GST part-price convention as other catalogue entries. The displayed estimate should state that GST is additional. This is a public estimate, not a garage quote or VIN-specific confirmation.

## v4 integration update
- v4 sample audit now finds Honda City front-left and rear-left door part-price rows; warnings are for missing replacement labour rates.
- v4 also finds Swift headlamp and Baleno front-bumper part prices; remaining warnings are labour-related.
- Five damaged sample outputs still have zero priced line items because the required labour and/or painting rates are absent. This is an incomplete estimate state, not a successful cost estimate.
- Contract B output files validate against `schemas/contract_b.schema.json`. The sample runner now performs this validation automatically.
