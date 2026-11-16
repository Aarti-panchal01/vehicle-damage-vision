# Policy Retrieval and Automated Claim Generation

*IEEE-style report input for integration into the team's final paper. Prepared by Nakshathira B for Role 3.*

## Contribution record

| Contributor | SRN | Work recorded for the report |
|---|---|---|
| Nakshathira B (`@nakshathira200-svg`) | PES2UG24AM096 | Policy document collection and source tracking; PDF extraction and preprocessing; chunking comparison; BGE-small embeddings; ChromaDB and BM25 hybrid retrieval; insurer-aware retrieval; Gemini-based claim writing; Contract B to Contract C validation; retrieval and groundedness evaluation. |

## I. Literature review

### A. Automated vehicle damage assessment and claim generation

Kumar and Sountharrajan present YUNet_LLMClaimReport, a framework that combines vehicle damage analysis with automated insurance claim report generation [1]. The system uses YOLOv11 for object detection, U-Net for damage segmentation, and a fine-tuned GPT-3.5-turbo model to generate claim reports from visual and textual information. The authors evaluate the framework using an automobile damage image dataset and insurance claim report data. They report a mAP@50 of 0.9424, an IoU of 0.85 and claim report accuracy of approximately 0.92. The study is relevant because it demonstrates how damage information can be carried beyond image detection into claim documentation. At the same time, the authors report factual inconsistencies in a portion of the generated reports. This reinforces the need to check generated insurance statements against reliable evidence rather than treating fluent output as proof of correctness.

Pérez-Zarate et al. study automated car damage assessment in an insurance-company setting [2]. Their approach combines multiple YOLO-based detectors, optimises confidence thresholds and fuses bounding-box predictions. The aim is to detect damage while keeping false positives low and maintaining practical inference speed. The study also presents TartesiaDS, a small public dataset containing images of damaged and undamaged vehicles labelled under the supervision of professional appraisers. Its insurance-focused evaluation is useful because an incorrect positive detection can lead to unnecessary inspection and claim-processing effort. The work primarily addresses visual damage verification, however, rather than policy interpretation or the generation of a policy-supported claim document.

### B. Retrieval-Augmented Generation for insurance documents

Lewis et al. introduced Retrieval-Augmented Generation (RAG), which combines a generative model with an external retrieval component [3]. Instead of relying only on information stored in model parameters, a RAG system retrieves relevant passages from a knowledge source and supplies them as context for generation. This is useful for document-based tasks where the answer depends on specific information contained in long or changing sources.

Hanmante, Patil and Shahade describe a multi-module RAG-based system for health insurance support [4]. Their work combines insurance assistance with policy recommendation and clause-level document retrieval, and includes an evaluator for assessing generated responses. Although the application is health insurance rather than motor insurance, the approach is relevant to the problem of retrieving policy clauses before generating explanations. It highlights the importance of making policy information accessible at clause level and assessing response quality rather than relying only on the language model's output.

### C. Relevance to the proposed module

The reviewed studies address complementary parts of insurance automation. Damage detection and report generation can reduce manual processing, while RAG can provide access to the specific policy wording needed to explain a claim. The Role 3 module focuses on this second requirement. It retrieves policy evidence for the selected insurer and generates claim explanations with source and page references. Numerical repair estimates remain the responsibility of the structured cost engine; the language model is not used to calculate or modify repair prices. This separation is important because a policy explanation must be supported by policy wording, while financial values must remain consistent with the upstream estimate.

## II. Methodology

### A. Module interface and workflow

Role 3 receives Contract A, which contains the vehicle and damage information, and Contract B, which contains the repair estimate produced by Role 2. The selected insurer and policy identity are used to constrain policy retrieval. The module produces Contract C, containing a claim summary, the original estimate line items and totals, policy justifications, relevant exclusions and a disclaimer.

The workflow consists of policy document loading, text extraction, chunking, embedding, hybrid retrieval, claim generation and output validation. Policy statements are based on retrieved evidence. Contract B's financial data is preserved programmatically rather than being recalculated by the language model.

### B. Policy document corpus

The final local corpus contains 10 PDF documents with approximately 284 pages. It includes eight insurer policy wordings and two official regulatory documents obtained from the Indian e-Gazette. The insurer policy wordings cover TATA AIG, ACKO, HDFC ERGO, SBI General, Universal Sompo, Liberty General, New India Assurance and Go Digit.

A source manifest records the document names and source URLs. Policy PDFs are retained locally and excluded from version control because of their size and distribution considerations. The manifest and corpus inventory are retained in the repository so that the source collection can be audited and reproduced. The collected corpus is a project-specific subset rather than a complete collection of Indian motor insurance regulations or all available policy products.

### C. PDF extraction and preprocessing

PDF text is extracted using PyPDF and pdfplumber. Layout-aware extraction is applied where required for multi-column documents. The extraction process retains page-level information and associates each page with metadata including source filename, insurer, policy name, UIN where available, page number and policy section or scope.

This metadata is important because policy passages that use similar terminology may belong to different insurers or products. Retaining source and page information also makes it possible to trace a generated explanation back to the original PDF.

### D. Chunking strategies

Two chunking strategies were implemented and compared.

**Fixed-size chunking:** Text is divided into chunks of approximately 500 tokens with an overlap of approximately 50 tokens. This approach produces consistently sized passages, but can split a policy clause or separate a condition from its exception.

**Clause-aware chunking:** The document structure is used to identify headings, sections and clause boundaries. The aim is to keep related policy text together while retaining page and section metadata. This approach better reflects how insurance policy documents are organised, although it can produce a larger number of shorter chunks.

Both methods were evaluated using the same 30-question coverage dataset. The better-performing strategy was selected for the canonical vector index.

### E. Embeddings and vector storage

The BAAI/bge-small-en-v1.5 sentence embedding model converts policy chunks and search queries into vector representations. ChromaDB stores the vectors together with the original chunk text and its metadata. Dense retrieval uses vector similarity to identify passages that are semantically related to the question, even where the query and policy wording do not use identical terms.

### F. Hybrid retrieval

Dense retrieval is combined with BM25 keyword retrieval. Dense retrieval captures semantic similarity, while BM25 gives weight to exact terms that are important in insurance wording, such as deductibles, exclusions, endorsements and consequential damage. Reciprocal Rank Fusion (RRF) combines the rankings produced by the two methods.

Where the insurer and policy identity are known, metadata filters constrain retrieval to the selected insurer or UIN. Candidate results are deduplicated and the system returns up to five unique evidence chunks. Each returned chunk retains its source document and page information for use by the claim writer.

### G. Claim generation and Contract C construction

The claim writer uses a Gemini model to generate the narrative and policy-justification portions of Contract C. It receives the damage context, selected insurer and policy identity, and the retrieved policy evidence. Its instructions require policy statements to be based only on the supplied evidence, to include source and page references, and to avoid presenting a policy clause as a guarantee that a claim will be accepted.

The Contract B object is validated before Contract C is constructed. The repair line items and monetary totals are copied programmatically into Contract C rather than regenerated by the language model. This design keeps policy interpretation separate from the numerical calculations performed by Role 2 and reduces the risk of a generated response changing estimate amounts. The final object is checked against the Contract C schema.

## III. Results

### A. Chunking comparison

The two chunking strategies were evaluated using the same 30 manually annotated coverage questions. The results are shown in Table I.

**TABLE I. CHUNKING STRATEGY COMPARISON**

| Metric | Fixed-size | Clause-aware |
|---|---:|---:|
| Number of chunks | 665 | 1,071 |
| Hit@1 | 0.4333 | 0.5667 |
| Hit@3 | 0.5333 | 0.6667 |
| Hit@5 | 0.6667 | 0.7333 |
| MRR@5 | 0.5078 | 0.6317 |

Clause-aware chunking performed better across all four retrieval metrics. Hit@5 increased from 0.6667 to 0.7333, while MRR@5 increased from 0.5078 to 0.6317. The result suggests that retaining policy clause and section boundaries can improve the ranking of relevant evidence. Clause-aware chunking was therefore selected for the final index.

### B. Retrieval evaluation

A gold set of 30 coverage questions was created across four insurers: TATA AIG (8 questions), ACKO (7), HDFC ERGO (7) and SBI General (8). Each question was manually associated with an expected insurer, policy UIN, page and section. A result counted as relevant only when these annotated fields matched.

The unfiltered baseline achieved Hit@1 of 0.4000, Hit@3 of 0.5667, Hit@5 of 0.6667 and MRR@5 of 0.5067. In the 150 result positions returned for the 30 questions, 59 results belonged to an insurer other than the expected insurer. This shows why semantic relevance alone is not sufficient for policy retrieval: a clause from another insurer may appear relevant while still being inapplicable to the selected policy.

A separate insurer-conditioned evaluation passed the known insurer to the retriever. As shown in Table II, this increased Hit@5 to 0.7667 and MRR@5 to 0.6567. No wrong-insurer results appeared among the 150 returned result positions in this filtered evaluation. This is the expected effect of insurer filtering and does not mean that every correct clause was retrieved; seven questions still missed the exact annotated source within the top five.

**TABLE II. UNFILTERED AND INSURER-CONDITIONED RETRIEVAL**

| Metric | Unfiltered baseline | Insurer-conditioned |
|---|---:|---:|
| Hit@1 | 0.4000 | 0.6000 |
| Hit@3 | 0.5667 | 0.6667 |
| Hit@5 | 0.6667 | 0.7667 |
| MRR@5 | 0.5067 | 0.6567 |
| Wrong-insurer result positions | 59 of 150 | 0 of 150 |

The insurer-conditioned results varied by insurer. Hit@5 was 1.0000 for ACKO, 0.2857 for HDFC ERGO, 1.0000 for SBI General and 0.7500 for TATA AIG. HDFC ERGO was the weakest group in this evaluation, indicating that policy-specific retrieval still requires improvement for some documents and sections.

### C. Claim generation and estimate preservation

A Gemini-based claim writer was integrated with the retrieval pipeline and successfully produced a Contract C output in a live smoke test. The claim writer uses the retrieved policy evidence for policy explanations, while the adapter transfers Contract B line items and totals programmatically.

The adapter was tested against five Contract B fixture outputs. The tests verify that the claim identifier, repair line items and monetary totals are preserved when constructing Contract C. This is a structural and numerical-preservation check; it does not establish that every generated policy explanation is semantically correct.

### D. Human groundedness review

The human groundedness review is **not complete**. The saved artifacts contain 20 policy-conditioned outputs based on five distinct Contract A and Contract B pairs; these are synthetic policy assignments, not 20 genuine insurer-linked claims. The outputs contain 186 policy-justification statements, and the human review worksheet still marks their support and over-interpretation judgments as `Pending`.

Automated checks confirm source and page traceability for the saved outputs, but text overlap does not establish semantic support. No human groundedness verdict counts are reported. The worksheet and automated evaluation artifacts are retained under `data/evaluation/groundedness/`; the pending rows must be reviewed before claiming groundedness.

### E. Software tests

The Role 3 implementation includes tests for document processing, policy-scope classification, chunking, retrieval evaluation, claim generation and Contract B to Contract C validation. At this revision, the full project test suite completed with 299 passing tests. These tests verify software behaviour and interface preservation; they do not replace the manual review of policy-statement meaning.

## Limitations

The retrieval evaluation contains 30 manually annotated questions and covers four insurers. It is a controlled project evaluation rather than a broad estimate of performance across all motor insurance policies. Exact page and section matching is intentionally strict, but it can fail to count a relevant continuation passage if the continuation appears on a page that was not separately annotated.

The 10-document corpus does not represent every applicable IRDAI circular or a complete standalone motor-tariff depreciation reference. Some planned regulatory sources could not be obtained from the available official links, and these gaps are recorded in the corpus inventory. Results should therefore be interpreted within the documents actually collected.

The pending human groundedness review covers 186 statements across 20 insurer-conditioned drafts, but those drafts are based on only five distinct Contract A and Contract B input pairs. It is not equivalent to testing 20 independent claim scenarios. No human verdicts or separate LLM-as-a-judge results are available. Policy interpretation can also depend on the complete policy schedule, endorsements and claim-specific facts, which may not all be represented in a retrieved excerpt.

The current module produces a preliminary, evidence-supported claim draft. It does not make a binding coverage decision, guarantee claim acceptance or replace review by an insurer or qualified surveyor.

## References

[1] P. Anand Kumar and S. Sountharrajan, “YUNet_LLMClaimReport: An Enhanced Automobile Insurance Fraud Detection and Automated Claim Report Generation Using Large Language Models,” *IEEE Access*, vol. 13, pp. 121935–121954, 2025, doi: 10.1109/ACCESS.2025.3584927.

[2] S. A. Pérez-Zarate, D. Corzo-García, J. L. Pro-Martín, J. A. Álvarez-García, M. A. Martínez-del-Amor and D. Fernández-Cabrera, “Automated Car Damage Assessment Using Computer Vision: Insurance Company Use Case,” *Applied Sciences*, vol. 14, no. 20, Art. no. 9560, 2024, doi: 10.3390/app14209560.

[3] P. Lewis *et al*., “Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks,” in *Advances in Neural Information Processing Systems*, vol. 33, pp. 9459–9474, 2020.

[4] S. Hanmante, S. Patil and A. K. Shahade, “A Multi Module A.I. System for Intelligent Health Insurance Support Using Retrieval Augmented Generation,” *Scientific Reports*, vol. 16, Art. no. 1403, 2026, doi: 10.1038/s41598-025-31038-6.
