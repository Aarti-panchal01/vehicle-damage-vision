# Insurer-scoped policy retrieval evaluation

## Mode and method

This is an **insurer-conditioned evaluation**, not unrestricted cross-insurer search. Each gold question's known insurer was passed to the existing retriever. Results were relevant only when insurer, policy UIN, page number, and policy section exactly matched an annotated expected source. Metrics use the top five results; MRR is MRR@5. The original gold set and baseline results were not changed.

## Metrics and baseline comparison

| Metric | Original unfiltered baseline | Insurer-scoped | Change |
|---|---:|---:|---:|
| Hit@1 | 0.4000 | 0.6000 | +0.2000 |
| Hit@3 | 0.5667 | 0.6667 | +0.1000 |
| Hit@5 | 0.6667 | 0.7667 | +0.1000 |
| MRR@5 | 0.5067 | 0.6567 | +0.1500 |

| Insurer | Questions | Hit@1 | Hit@3 | Hit@5 | MRR@5 |
|---|---:|---:|---:|---:|---:|
| ACKO | 7 | 0.8571 | 0.8571 | 1.0000 | 0.8929 |
| HDFC ERGO | 7 | 0.1429 | 0.2857 | 0.2857 | 0.2143 |
| SBI General | 8 | 0.8750 | 0.8750 | 1.0000 | 0.9000 |
| TATA AIG | 8 | 0.5000 | 0.6250 | 0.7500 | 0.5938 |

There were **0 wrong-insurer result slots** among 150 scoped results and **0 results with missing required metadata**. The zero wrong-insurer count follows from insurer filtering; it does not itself establish retrieval quality. Exact page/section relevance was still only Hit@5 0.7667, with seven misses.

## Questions still failing Hit@5

| ID | Question | Observed results |
|---|---|---|
| TATA-01 | Under TATA AIG Auto Secure, which listed events can trigger Section I cover for damage to the insured vehicle? | The top results were TATA AIG page 1 General Policy Text, page 4 Section I, and page 49 Definitions; the expected page 1 Section I chunk was not returned. |
| TATA-05 | For a TATA AIG Section I vehicle-damage claim, where is the applicable deductible amount specified? | No exact page 6 / Deductibles result appeared in the top five. |
| HDFC-01 | Which listed perils does HDFC ERGO Section I name for loss or damage to the insured vehicle? | Page 2 Section I ranked first, but the expected page 1 / Section I source was absent. |
| HDFC-02 | Under HDFC ERGO Section II, what liability arising from use of the insured vehicle can be indemnified? | The expected page 3 / Section II source was absent from the top five. |
| HDFC-03 | What percentage of the HDFC ERGO owner-driver personal accident sum is payable for death? | Personal-accident results appeared, but not the expected page 4 / Section III source. |
| HDFC-04 | At what point does an HDFC ERGO policyholder become entitled to No Claim Bonus according to the policy wording? | No exact page 7 / No Claim Bonus source appeared in the top five. |
| HDFC-05 | How does HDFC ERGO say a claim intimation is made and what accident details are captured? | Claims Procedure page 10 ranked first, but the expected page 9 source did not appear. |

## Examples

- Successful: ACKO-01 retrieved its expected Section I page 5 at rank 1. TATA-04 retrieved the expected Section III page 5 at rank 1. HDFC-06 retrieved the expected Claims Procedure page 9 at rank 2.
- Unsuccessful: HDFC-05 returned only HDFC ERGO documents, but Claims Procedure page 10 ranked first and the expected page 9 was absent. This illustrates why correct insurer metadata alone is not sufficient.

## Interpretation and limitations

Scoping improved all four aggregate metrics against the unrestricted baseline and removed wrong-insurer results. This indicates a useful improvement when the caller already knows the insurer. It does not measure insurer identification or unrestricted search quality. Exact page-and-section matching remains strict: adjacent pages or sections are not treated as relevant unless listed as verified sources. HDFC ERGO remains the weakest insurer slice, at Hit@5 0.2857. No embedding, ranking, or chunking parameters were changed.

## Reproduction

```sh
HF_HUB_OFFLINE=1 ./.venv/bin/python -m src.rag.evaluate_retrieval --insurer-scoped
```

Results are in `data/evaluation/retrieval_results_scoped.json`. The verified existing 516-record Chroma index was reused; no rebuild was performed.
