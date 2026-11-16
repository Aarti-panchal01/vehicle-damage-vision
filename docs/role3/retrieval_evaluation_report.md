# Role 3 policy retrieval evaluation

## Dataset and source verification

The version-controlled gold set contains exactly 30 questions: TATA AIG 8, ACKO 7, HDFC ERGO 7, and SBI General 8. Topics include own-damage cover, exclusions and deductibles, third-party liability, personal accident, claim handling, No Claim Bonus, add-ons, and endorsements. Each record includes the policy UIN, an exact expected page/section/scope tuple, a short evidence excerpt, and the original PDF filename.

All evidence excerpts were checked against the named original PDF's extracted page text and against a chunk carrying the annotated page, section, and scope. The checked files were the four PDFs under `data/policy_docs/`. The set contains one verified relevant source per question; the schema permits multiple expected sources if a question requires them.

## Method

The evaluation script loads the existing hybrid retriever and requests its top five results for each question. Queries are intentionally unfiltered by insurer or UIN so incorrect-insurer results are visible. A result counts as relevant only when insurer, UIN, page number, and policy section all exactly match an expected source. Approximate page or section matches do not count. Metrics are Hit@1, Hit@3, Hit@5, and MRR@5 (reciprocal rank of the first relevant result among the returned five).

## Baseline results

| Insurer | Questions | Hit@1 | Hit@3 | Hit@5 | MRR@5 |
|---|---:|---:|---:|---:|---:|
| **Overall** | **30** | **0.4000** | **0.5667** | **0.6667** | **0.5067** |
| ACKO | 7 | 0.8571 | 0.8571 | 0.8571 | 0.8571 |
| HDFC ERGO | 7 | 0.0000 | 0.2857 | 0.2857 | 0.1429 |
| SBI General | 8 | 0.5000 | 0.6250 | 0.7500 | 0.5938 |
| TATA AIG | 8 | 0.2500 | 0.5000 | 0.7500 | 0.4313 |

The 150 returned result slots contained 59 results from an insurer other than the question's expected insurer (39.3%). No returned result was missing one of the six checked metadata fields: insurer, UIN, filename, page, section, or scope.

## Questions that missed Hit@5

| ID | Question | Observed retrieval issue |
|---|---|---|
| TATA-01 | Under TATA AIG Auto Secure, which listed events can trigger Section I cover for damage to the insured vehicle? | Target page 1 / Section I was absent from the top five; a TATA AIG page 1 general-text chunk and a page 4 Section I chunk ranked above it. |
| TATA-05 | For a TATA AIG Section I vehicle-damage claim, where is the applicable deductible amount specified? | No exact page 6 / Deductibles match; the top five favored unrelated TATA AIG definitions, add-on, and endorsement chunks. |
| ACKO-03 | Under ACKO Section II, within what territory does the policy cover specified legal liability arising from use of the insured vehicle? | ACKO Section II page 8 ranked second, but the exact expected source was page 7; the page-exact criterion therefore did not count it. |
| HDFC-01 | Which listed perils does HDFC ERGO Section I name for loss or damage to the insured vehicle? | HDFC Section I page 2 ranked first, but expected page 1 did not appear in the top five. |
| HDFC-02 | Under HDFC ERGO Section II, what liability arising from use of the insured vehicle can be indemnified? | Expected page 3 did not appear in the top five; an HDFC Section II page 4 chunk ranked third. |
| HDFC-03 | What percentage of the HDFC ERGO owner-driver personal accident sum is payable for death? | Expected page 4 did not appear; HDFC personal-accident chunks on pages 17 and 5 ranked highest. |
| HDFC-04 | At what point does an HDFC ERGO policyholder become entitled to No Claim Bonus according to the policy wording? | Expected page 7 / No Claim Bonus did not appear in the top five; page 8 general text ranked first. |
| HDFC-05 | How does HDFC ERGO say a claim intimation is made and what accident details are captured? | Expected page 9 / Claims Procedure did not appear; page 10 Claims Procedure ranked first. |
| SBI-01 | Which events does SBI General list as insured causes of accidental loss or damage under Section I? | Expected page 2 / Section I did not appear; the top five contained unrelated SBI pages and sections. |
| SBI-03 | Under SBI General Section II, what categories of third-party liability can arise from use of the insured vehicle? | No SBI General result appeared in the top five; other insurers' Section II chunks were returned. |

## Retrieval examples

- Successful: ACKO-01 returned the expected ACKO Section I page 5 chunk at rank 1. SBI-06 returned the expected SBI compulsory-deductible endorsement page 8 at rank 1. TATA-04 returned the expected owner-driver personal-accident page 5 at rank 1.
- Unsuccessful: TATA-03 returned the expected Section II page 4 at rank 4, after three ACKO results and a TATA AIG page 49 result. It therefore missed Hit@3 but counted for Hit@5.
- Insurer mixing: for TATA-02, the ACKO depreciation chunk ranked first and HDFC ERGO and SBI General depreciation chunks also appeared in the top five; the TATA AIG page 2 gold source ranked second.

## Vector index and limitations

The initial Chroma collection was stale: it contained 415 records, versus 516 current clause-aware chunks, with 101 current chunk IDs missing and widespread section/scope metadata differences. It was rebuilt once through the existing retriever index method. The rebuilt index has 516 records and its IDs exactly match the current clause-aware dataset.

This is a 30-question baseline, not a broad quality estimate. Relevance intentionally uses exact page and section metadata; a correct continuation on an adjacent page may not count unless that page was independently annotated as relevant. The unfiltered setup exposes cross-insurer confusion and does not represent a production query that applies an insurer filter. No parameter tuning was performed. A next step after review could be a separately reported filtered evaluation and analysis of insurer-mixing and page-boundary retrieval errors; the baseline above should remain unchanged.

## Reproduction

Index rebuilt once with:

```sh
./.venv/bin/python -c 'from src.rag.retriever import HybridPolicyRetriever; r=HybridPolicyRetriever(); print("reindexed", r.rebuild_index())'
```

Evaluation command:

```sh
HF_HUB_OFFLINE=1 ./.venv/bin/python -m src.rag.evaluate_retrieval
```

The offline flag uses the already downloaded configured BGE-small model. Results are written to `data/evaluation/retrieval_results.json`.

## Complete question list

| ID | Gold question |
|---|---|
| TATA-01 | Under TATA AIG Auto Secure, which listed events can trigger Section I cover for damage to the insured vehicle? |
| TATA-02 | For a TATA AIG insured vehicle older than six months but no more than one year, what depreciation rate applies to replaced parts? |
| TATA-03 | Under TATA AIG Section II, what type of third-party property damage is indemnified, and what property is excluded? |
| TATA-04 | Under TATA AIG's owner-driver personal accident cover, what scale percentage is payable for death? |
| TATA-05 | For a TATA AIG Section I vehicle-damage claim, where is the applicable deductible amount specified? |
| TATA-06 | How soon does TATA AIG require written notice after accidental loss or damage, and what must happen to claim correspondence? |
| TATA-07 | When does TATA AIG allow No Claim Bonus at renewal under its Auto Secure policy wording? |
| TATA-08 | Under TATA AIG IMT24, what fitting loss is covered and what breakdown-related loss is excluded? |
| ACKO-01 | Under ACKO's Section I wording, which engine parts can be damaged by coolant or lubricating-oil leakage for the accidental-leakage cover? |
| ACKO-02 | What depreciation rate does ACKO apply to replaced parts for a vehicle over four and up to five years old? |
| ACKO-03 | Under ACKO Section II, within what territory does the policy cover specified legal liability arising from use of the insured vehicle? |
| ACKO-04 | For ACKO Engine Protect – Flood, which internal vehicle assemblies can qualify for repair or replacement expenses after water-ingress damage? |
| ACKO-05 | What key or lock-set events can trigger ACKO Key Protect reimbursement, subject to the schedule amount? |
| ACKO-06 | If an ACKO-insured vehicle is immobilized by a flat tyre and roadside assistance is opted for, what assistance does the wording provide? |
| ACKO-07 | Under ACKO's Voluntary Deductible add-on, how much of each own-damage loss does the insured agree to bear? |
| HDFC-01 | Which listed perils does HDFC ERGO Section I name for loss or damage to the insured vehicle? |
| HDFC-02 | Under HDFC ERGO Section II, what liability arising from use of the insured vehicle can be indemnified? |
| HDFC-03 | What percentage of the HDFC ERGO owner-driver personal accident sum is payable for death? |
| HDFC-04 | At what point does an HDFC ERGO policyholder become entitled to No Claim Bonus according to the policy wording? |
| HDFC-05 | How does HDFC ERGO say a claim intimation is made and what accident details are captured? |
| HDFC-06 | Within what maximum time after receiving claim intimation does HDFC ERGO say a surveyor will be assigned? |
| HDFC-07 | Under HDFC ERGO IMT24, what is covered for scheduled electrical or electronic fittings, and what limit applies? |
| SBI-01 | Which events does SBI General list as insured causes of accidental loss or damage under Section I? |
| SBI-02 | For an SBI General vehicle over four and up to five years old, what depreciation rate applies to replaced parts? |
| SBI-03 | Under SBI General Section II, what categories of third-party liability can arise from use of the insured vehicle? |
| SBI-04 | What compensation scale does SBI General state for death under owner-driver personal accident cover? |
| SBI-05 | How long after expiry can SBI General's No Claim Bonus wording allow renewal while retaining NCB eligibility? |
| SBI-06 | Under SBI General IMT16, what deductible obligation applies to each Section I event, including a total loss? |
| SBI-07 | Under SBI General's electrical/electronic fittings cover, how is cover for fittings outside the manufacturer's listed price arranged? |
| SBI-08 | What does SBI General's Additional Road-Side Assistance section say about the services it provides and where those services apply? |
