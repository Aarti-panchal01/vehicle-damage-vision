# Role 2 — Material and depreciation audit

Audit date: 2026-11-09

## Depreciation calculation review

The engine reads `depreciation_rules.json` and applies the configured percentage to the replacement-part amount. Metal age bands are evaluated as half-open intervals (`min_age_years <= age < max_age_years`), with the final band open-ended. At exact boundaries, the next band applies: 0.5 years -> 5%; 1 year -> 10%; 2 years -> 15%; 3 years -> 25%; 4 years -> 35%; 5 years -> 40%; 10 years -> 50%.

For paint, the configured calculation is 50% depreciation on 25% of the consolidated all-in paint bill. This is not 50% of the entire paint bill. The current `depreciation_pct` field in Contract B represents the part-material rate; `depreciation_amount` includes both part depreciation and the separately calculated paint-material depreciation.

## Policy limitation

The values are transcribed from the Shriram General Insurance Stand-Alone Motor Own Damage Private Car Policy wording identified in `depreciation_rules.json` (Section 1, PDF page 1). This is evidence for that wording only. It does not establish that the same rates apply to another insurer, another policy/UIN, add-on, endorsement, or claim date. Before producing a real claim estimate, Role 3 / the claim workflow must identify the applicable policy and confirm its depreciation clause. Do not describe these rates as universally mandated or universally IRDAI rates.

## Material classification review

The part-price CSV currently contains explicit material labels for its listed parts. `unknown` material remains intentionally unresolved and the engine refuses to calculate depreciation for it. In particular, the Nexon headlamp and tail-lamp rows are marked `unknown`; do not change them to plastic based only on appearance or general vehicle knowledge. Obtain a source that identifies the material or a manufacturer/dealer specification first.

The other labels (plastic, metal, glass) are database classifications, not independent laboratory verification. Preserve the source and fitment notes. Recheck them against OEM/dealer documentation when available.

## Current known classification / compatibility flags

- Swift right outside mirror: material `unknown` and price-source conflict remains unresolved; do not use.
- Nexon headlamp and tail lamp: material `unknown`; do not use for a depreciated estimate.
- Swift right headlamp: year range parses for the 2021 sample, but the CSV explicitly says compatibility must be verified.
- Baleno front bumper: generation/VIN/variant compatibility must be confirmed.
- Honda City door prices: published estimates for the 4th-generation listing; verify 2019 variant/VIN fitment.

## Review conclusion

The arithmetic implementation is covered by unit tests, but policy applicability and several material / fitment labels remain evidence limitations. These limitations must remain visible in any review or claim output.
