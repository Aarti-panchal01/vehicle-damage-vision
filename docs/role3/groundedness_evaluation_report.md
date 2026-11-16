# Role 3 claim-draft groundedness evaluation

## Scope and case count

The repository has **5 distinct Contract A + Contract B pairs** with matching claim IDs: `CLM-20261020-001` through `CLM-20261020-005`. All five have a matching Contract A mock. Neither Contract A nor Contract B contains insurer or policy UIN, so there are **0 genuinely insurer-linked claim cases** available. The corpus registry/index supplies four valid policy identities, but selecting one for a claim is not established by the input data.

To exercise the implemented integration without representing guesses as real policy assignments, the pipeline was run once per real input pair against each of the four corpus policies. This produced **20 synthetic policy-conditioned integration scenarios**, clearly labeled as such in the manifest. These are not 20 distinct real insurer-linked claims; the 20-claim genuine groundedness requirement remains incomplete.

## Generation and automated checks

| Check | Result |
|---|---:|
| Synthetic policy-conditioned scenarios generated | 20 / 20 (100%) |
| Generation failures | 0 / 20 (0%) |
| Contract C schema-valid, with exact top-level field set | 20 / 20 (100%) |
| All retrieved evidence identity metadata matched requested insurer/UIN | 20 / 20 (100%) |
| Contract B line items, totals, currency, age, and unpriced parts preserved exactly | 20 / 20 (100%) |
| Disclaimer included non-decision, no-guarantee, and Shriram depreciation caveats | 20 / 20 (100%) |
| Real examples with nonempty `unpriced_parts` | 0 / 20 |
| Exclusion flags emitted | 0 across 20 drafts |

The incomplete-estimate disclaimer branch is present in the implementation, but none of the five supplied Contract B samples has nonempty `unpriced_parts`; its behavior could not be verified with a real sample in this evaluation.

## Citation traceability

There are **186 policy justification entries** across the 20 drafts.

- Source file exists in the local policy corpus: **186 / 186 (100%)**.
- Page number resolves to a page in that source: **186 / 186 (100%)**.
- Retrieved metadata agrees with the source filename/page in the citation: **186 / 186 (100%)**.
- Entire generated excerpt matches normalized extracted page text verbatim: **132 / 186 (71.0%)**.
- At least an 80-character contiguous excerpt from every generated statement was found on its cited page: **186 / 186 (100%)**.

The 54 whole-excerpt mismatches (29.0%) include chunk formatting/header differences and excerpt truncation. The worksheet supplies an exact source-overlap fragment for reviewer convenience; overlap confirms textual traceability only. It does **not** establish that the complete statement is semantically correct or not over-interpreted. Semantic groundedness remains unscored pending human review; no 100% groundedness claim is made.

## Exclusions and semantic review

No exclusion flags were produced. Therefore there are no generated exclusion statements to score for explicit source support or accident-fact relevance. This is not evidence that the claims have no applicable exclusions; the deterministic flagger is conservative and may miss relevant clauses.

The human worksheet has **186 rows**, one per policy justification, and leaves support and over-interpretation judgments as **Pending**. Any exclusion-specific review fields are also Pending. A reviewer must assess each statement and any later exclusion flags before relying on these drafts.

## Preliminary AI-assisted triage

This screening pass does not replace human review and does not change any worksheet verdict. On 2026-11-16, the four official insurer PDFs listed in `data/policy_docs/sources.csv` were downloaded temporarily and compared with the cited excerpts. Each downloaded PDF contained the insurer UIN recorded in the source manifest.

- The normalized first 80 characters of the stored excerpt matched the cited PDF page for **131 of 186** rows: ACKO 48/48, HDFC ERGO 47/47, TATA AIG 14/49, and SBI General 22/42.
- The exact-prefix check did not match for the other **55** rows: TATA AIG 35 and SBI General 20. All 55 still had at least 92.86% distinct-token overlap with their cited page. Treat these as extraction or formatting differences to verify, not confirmed citation errors.
- A page-text match does not show that a clause applies to a particular loss. The statements mostly repeat retrieved policy wording, and Contract A/B do not establish the real insurer, UIN, schedule, or endorsements for these claims.

Triage priority: first verify the 55 exact-prefix mismatches against the intended policy version and page; then review all 186 statements for relevance to the claim facts, missing conditions, and over-interpretation. Keep `supports_statement`, `over_interpreted`, and the exclusion-review fields `Pending` until a human signs them off. The temporary PDF copies were not added to the repository.

## Limitations and next steps

1. The 20 runs are synthetic policy assignments using real claim inputs. The source records do not identify which insurer/UIN actually covers any claim. Obtain that identity from the claim/customer source before counting insurer-specific claims as genuine.
2. Five distinct real input pairs are available, fewer than the target of 20.
3. Whole-excerpt text matching failed for 54 citations; the exact excerpt fragment was found, but source alignment and semantic support still require review.
4. The supplied samples do not exercise nonempty unpriced-parts handling.
5. Human semantic review is pending for all 186 justification rows. Review whether each excerpt supports its full statement and whether the wording over-interprets the clause.
6. No claim approval, coverage determination, or settlement value can be inferred from these drafts.

## Artifacts

- Contract C drafts: `data/evaluation/groundedness/generated_claims/`.
- Input/policy identity and retrieved metadata manifest: `data/evaluation/groundedness/groundedness_manifest.jsonl`.
- Automated check counts: `data/evaluation/groundedness/automated_summary.json`.
- Human review worksheet: `data/evaluation/groundedness/human_review.csv`.

## Continuation audit status

The groundedness artifacts were already present before this continuation. A read-only audit confirmed 20 saved Contract C outputs across five claim IDs, with each input paired against four insurer policies. All 20 saved outputs passed Contract C validation, exact top-level key checks, manifest insurer/UIN and cited source/page traceability checks, and Contract B estimate-field equality checks. These remain 20 synthetic policy-conditioned scenarios over **5 distinct claim pairs**, not 20 distinct genuine insurer-linked claims.

The preliminary triage above does not regenerate the 20 saved drafts or establish their provider provenance. The existing manifest does not record a model identifier or per-call execution time, so those details cannot be verified or reported. The five A/B pairs still do not identify the actual insurer/UIN for each claim; do not count their synthetic policy assignments toward the 20-claim target.

An LLM-as-judge comparison was not run because no Gemini configuration was available in this process. Human review remains Pending for all 186 justification rows. To complete a genuine insurer-conditioned evaluation, obtain the policy insurer/UIN for each claim from the claim source and at least 15 additional distinct matching Contract A/Contract B pairs from Roles 1 and 2. Then run and record one generation per genuine pair, including model identifier and duration.

The saved Contract C JSON files and manifest do not contain a provider response ID, model identifier, prompt/response log, or per-call timing. Their contents alone do not prove that these 20 drafts came from actual Gemini API responses. The separate Gemini smoke-test result does not establish provenance for this batch. Actual Gemini generation for the existing drafts is therefore unverified.
