# Role 3 Contract B → Contract C claim-draft pipeline

## Verified Contract B

The copied Role 2 schema is `schemas/contract_b.schema.json` (Draft 2020-12). It requires exactly `claim_id`, `currency`, `vehicle_age_years`, `line_items`, `totals`, and `unpriced_parts`; `currency` is `INR`. Each line item requires `part`, `action`, `material`, `part_cost`, `labour_cost`, `paint_cost`, `depreciation_pct`, `depreciation_amount`, `claimable_amount`, and `price_source`. `totals` requires `gross`, `depreciation`, and `claimable`. The provided Role 2 sample `contract_a_001_dev_01_contract_b.json` validates against the schema.

## Exact mapping

| Contract C field | Source and handling |
|---|---|
| `claim_id` | Contract A and B `claim_id`; mismatch is rejected. |
| `line_items` | Deep copy of Contract B `line_items`, unchanged. |
| `totals.gross` | Contract B `totals.gross`, unchanged. |
| `totals.depreciation` | Contract B `totals.depreciation`, unchanged. |
| `totals.claimable` | Contract B `totals.claimable`, unchanged. |
| `totals.currency` | Contract B `currency`, preserved as Contract C totals metadata. |
| `totals.vehicle_age_years` | Contract B `vehicle_age_years`, preserved as metadata. |
| `totals.unpriced_parts` | Contract B `unpriced_parts`, deep copied, including an empty list. |

Contract C permits additional properties within `line_items` and `totals`, so this mapping is schema-compatible. The adapter returns only these estimate-related fields; it does not create summary, justification, exclusions, or disclaimer content.

## Public adapter and pipeline interfaces

`src/rag/claim_writer.py` exposes:

- `load_contract_b_schema()` — loads and checks the copied schema.
- `validate_contract_b(contract_b)` — raises `ValueError` with validation paths for invalid input.
- `check_matching_claim_ids(contract_a, contract_b)` — returns the shared ID or raises `ValueError`.
- `build_contract_c_estimate_fields(contract_a, contract_b)` — returns new mapped objects without mutating either input.
- `validate_contract_c_estimate_fields(fields)` — checks the mapped keys against the Contract C property schemas.
- `generate_claim_draft(contract_a, contract_b, insurer, uin, retriever=None, top_k=5)` — validates inputs, retrieves policy evidence for the exact selected identity, and emits a full schema-validated Contract C draft.
- `run_role3_pipeline(contract_a, contract_b, insurer, policy_uin, retriever=None, top_k=5)` in `src/rag/pipeline.py` — public pipeline wrapper.
- `retrieve_policy_evidence(...)` — constructs claim-focused queries and calls `HybridPolicyRetriever.retrieve` with both `insurer` and `uin` filters. Evidence with mismatched identity is rejected; no fallback is attempted.

## Gemini narrative generation

The claim narrative now uses one Gemini Flash API invocation per claim request. Configure `GEMINI_API_KEY` and `GEMINI_MODEL` in the runtime environment; `.env.example` lists the variable names without credentials or a hard-coded model identifier. The client dependency is `google-genai`.

The single request includes Contract A, Contract B, selected insurer and UIN, retrieved top policy chunks, and the complete Contract C JSON Schema. The system prompt limits policy assertions to supplied chunks, requires source/page citations, forbids invented policy details and coverage guarantees, asks for fact-relevant potential exclusions only, and requests Contract C JSON. The response is parsed once; malformed JSON, invalid narrative fields, or citations to a source/page outside the retrieved evidence raise a clear generation error. There is no deterministic narrative fallback.

The model-produced `claim_id`, `line_items`, and `totals` are ignored. The existing estimate adapter restores those fields from validated Contract A/B, after which the complete object is validated against Contract C. This protects all monetary fields from model changes.

## Evidence and draft behavior

Queries use the Contract A accident description, damaged parts/types/notes, and Contract B repair actions/parts. Three query intents cover relevant coverage, exclusions/limitations, and claim conditions/deductibles. Retrieved evidence retains insurer, UIN, source filename, page, section, scope, text, and score when available. Contract C justifications quote clipped retrieved wording with its source filename and actual page. Empty evidence or any identity mismatch fails safely.

The summary labels damage facts as Contract A input, repair actions/amount as Contract B input, and refers to policy wording separately in cited evidence. Exclusions are flagged only when retrieved wording contains an exclusion cue and a supported named subject also appears in the supplied accident facts; any flag is explicitly potential and requires review. This deterministic relevance check is conservative and may miss exclusions requiring semantic interpretation.

The disclaimer states that the draft is not an insurer decision, requires insurer verification, and that retrieved wording is not a coverage or settlement guarantee. It notes the Shriram-origin depreciation assumption and, when `unpriced_parts` is nonempty, that the estimate is incomplete and the claimable amount is not approved or guaranteed payable.

## Preservation and limitations

The adapter does not calculate, round, recast, normalize, or otherwise change monetary values. It copies every line-item field and all three totals exactly. It preserves `currency`, `vehicle_age_years`, and `unpriced_parts` within the Contract C `totals` object, using the schema's permitted additional properties.

Role 2's handoff says its depreciation values are based on one Shriram policy and are not universal across insurers. The supplied values must be preserved as-is, but their applicability must be independently checked against the selected policy. This adapter makes no coverage or depreciation-validity assertion.

Nonempty `unpriced_parts` remains present in the mapped totals metadata and triggers the incomplete-estimate disclaimer. The claimable total is not described as approved or final payable value.

## Validation

The Contract A and B schemas are applied before generation. Claim IDs must match. The estimate mapping is checked against Contract C properties, and the complete draft is validated against the Contract C schema before return. Inputs and estimate values are not modified.

## Known limitations

- Gemini produces the summary and policy statements, but the prompt and citation checks do not establish semantic correctness. Human review is required.
- The pipeline does not determine coverage or provide legal advice.
- Exclusion flagging uses explicit lexical cues and is conservative; human review remains necessary.
- The retrieved-policy corpus may not include the selected policy. In that case the pipeline raises an error rather than switching policies.
- Real index retrieval requires the configured BGE model to be locally available or downloadable. Unit tests mock retrieval.
- Missing `GEMINI_API_KEY` or `GEMINI_MODEL` is a configuration error. API failures and malformed/invalid responses fail the request rather than falling back to a template.
