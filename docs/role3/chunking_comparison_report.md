# Chunking Strategy Comparison

## Corpus and processing

Processed 10 PDFs and 284 pages: 269 insurer-policy pages and 15 regulatory pages.
The original 30-question gold set and its annotations were used unchanged. Retrieval was insurer- and UIN-scoped; each returned result was relevant only when insurer, UIN, page, and section matched an annotated expected source.

| Strategy | Chunks | Tokens min / mean / median / p95 / max | Hit@1 | Hit@3 | Hit@5 | MRR@5 |
|---|---:|---|---:|---:|---:|---:|---:|
| Fixed-size | 665 | 29 / 408.17 / 500 / 500 / 500 | 0.4333 | 0.5333 | 0.6667 | 0.5078 |
| Clause-aware | 1071 | 4 / 230.77 / 220 / 472 / 498 | 0.5667 | 0.6667 | 0.7333 | 0.6317 |

Both strategies used BAAI/bge-small-en-v1.5, the existing BM25 implementation, hybrid RRF, and top five results. Each comparison index was isolated and built once.

## Per-insurer results

| Insurer | Questions | Fixed Hit@5 | Fixed MRR@5 | Clause Hit@5 | Clause MRR@5 |
|---|---:|---:|---:|---:|---:|
| ACKO | 7 | 0.7143 | 0.6429 | 0.8571 | 0.8571 |
| HDFC ERGO | 7 | 0.5714 | 0.3500 | 0.2857 | 0.2143 |
| SBI General | 8 | 0.8750 | 0.5979 | 1.0000 | 0.9000 |
| TATA AIG | 8 | 0.5000 | 0.4375 | 0.7500 | 0.5312 |

## Failures and scope checks

- Fixed-size failed Hit@5: TATA-05, TATA-06, TATA-07, TATA-08, ACKO-03, ACKO-07, HDFC-02, HDFC-03, HDFC-07, SBI-01.
- Clause-aware failed Hit@5: TATA-01, TATA-05, ACKO-03, HDFC-01, HDFC-02, HDFC-03, HDFC-04, HDFC-05.
- Wrong-insurer result slots: fixed 0; clause-aware 0.
- Wrong-UIN result slots: fixed 0; clause-aware 0.
- Each strategy returned 150 result slots.

## Selection

Clause-aware chunking is selected for the canonical index. It improves Hit@5 by 0.0666 and MRR@5 by 0.1239 over fixed-size chunking. It also improves Hit@1 and Hit@3. Since the gains are not close, this selection follows measured retrieval performance rather than parameter tuning.

## Canonical index verification before repository cleanup

- Strategy: clause-aware; chunk source: `data/processed/clause_aware_chunks.jsonl`.
- Collection: `vehicle_insurance_policies` in `data/vector_db`; 1,071 unique indexed chunks.
- All 10 manifest filenames are represented. The canonical collection IDs exactly match the selected chunk IDs; no stale IDs were found.
- Both regulatory PDFs are represented with blank insurer and UIN metadata. Insurer/UIN scoped retrieval checks passed for each manifest entry with an identity.
- Chunk metadata checks found no required-field omissions and no regulatory identity assignments.
- The generated chunk files and ChromaDB index were removed from the working tree during repository cleanup. Recreate them from the local source PDFs with the commands above; they are not handoff files.

## Limitations

Clause-aware output includes a small number of short chunks (minimum 4 tokens), reflecting short source sections. HDFC ERGO remains the weakest insurer in this gold set (Hit@5 0.2857); eight clause-aware questions fail Hit@5 overall. The evaluation measures only the 30 supplied insurer-scoped questions and does not establish unrestricted cross-insurer performance.

## Artifacts

- Fixed-size results: `data/evaluation/chunking_fixed_results.json`.
- Clause-aware results: `data/evaluation/chunking_clause_results.json`.
- Gold set: `data/evaluation/retrieval_gold_set.jsonl` (unchanged).
