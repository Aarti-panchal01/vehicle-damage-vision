# Garage rate data — v7

Source: user-supplied workbook `Garage_car report.xlsx`, garage named LUSTRO Auto corp pvt ltd. Date recorded: 2026-11-10. Exact garage address and GST treatment were not supplied.

- `labour_rates.csv`: repair labour values are from the common repair-rate list. The garage did not specify whether those repair rates vary by vehicle; they are stored as `all` and should be treated as a provisional shared rate. For replacement labour, rates are vehicle-specific as supplied.
- `paint_rates.csv`: panel-wise rates are vehicle-specific. Where the garage supplied a range, the midpoint is used in `rate_inr` for deterministic calculations; the original range is preserved in the `source` field.
- The garage did not confirm whether painting includes primer/material. `includes_paint_material=yes` is a provisional modelling assumption so the existing Cost Engine can use the rate; this must be confirmed before treating depreciation of paint material as authoritative.
- No second-garage quotation was supplied. Do not describe simulated variations as independently collected garage data.
- Replacement spare-part prices and fitting labour remain separate. The garage's part-price ranges are not substituted for the online `parts_prices.csv` catalogue.

## Midpoint convention
For any quoted range a–b, the calculation rate is (a+b)/2. This is a deterministic modelling convention, not a new quote from the garage.

## Garage price variation note

The garage owner indicated that prices at other garages may vary only slightly across spare parts, labour, painting and related service charges. This is qualitative information only and is not an independently collected second-garage quotation. The existing LUSTRO rates are retained as reference estimates.
