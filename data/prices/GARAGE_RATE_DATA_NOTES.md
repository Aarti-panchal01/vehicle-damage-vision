# Garage rate data — v7

Source: user-supplied workbook `Garage_car report.xlsx`, garage named LUSTRO Auto corp pvt ltd. Date recorded: 2026-11-10. Exact garage address and GST treatment were not supplied.

- `labour_rates.csv`: repair labour values are from the common repair-rate list. The garage did not specify whether those repair rates vary by vehicle; they are stored as `all` and should be treated as a provisional shared rate. For replacement labour, rates are vehicle-specific as supplied.
- `paint_rates.csv`: panel-wise rates are vehicle-specific. Where the garage supplied a range, the midpoint is used in `rate_inr` for deterministic calculations; the original range is preserved in the `source` field.
- The garage did not confirm whether painting includes primer/material. `includes_paint_material=yes` is a provisional modelling assumption so the existing Cost Engine can use the rate; this must be confirmed before treating depreciation of paint material as authoritative.
- No second-garage quotation was supplied. Do not describe simulated variations as independently collected garage data.
- Replacement spare-part prices and fitting labour remain separate. The garage's part-price ranges are not substituted for the online `parts_prices.csv` catalogue.

## Midpoint convention
For any quoted range a–b, the calculation rate is (a+b)/2. This is a deterministic modelling convention, not a new quote from the garage.

## Honda City and Baleno modelled extensions (2026-11-10)
To avoid treating one garage's vehicle-specific rates as universal, the project adds provisional modelled rates for two additional models. These are explicitly NOT garage quotations:
- Honda City (model key `City`): comparable Creta replacement-labour and panel-painting midpoints adjusted upward by 5%.
- Maruti Baleno (model key `Baleno`): comparable Swift replacement-labour and panel-painting midpoints adjusted downward by 5%.
- Every added row is labelled `MODELLED ESTIMATE — NOT A GARAGE QUOTE`; the `source` field records the proxy model and adjustment.
- Paint-material inclusion remains unconfirmed; the existing `yes` flag is a computational assumption only, not a statement confirmed by the garage.
- These values are suitable only for provisional demo/testing and must be replaced or validated with model-specific garage/OEM quotations before real claim settlement.
