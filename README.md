# ClaimFrame

*A clearer first draft for every vehicle claim.*

[![Project CI](https://github.com/Aarti-panchal01/vehicle-damage-vision/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Aarti-panchal01/vehicle-damage-vision/actions/workflows/ci.yml)

**ClaimFrame is a team-built prototype for turning vehicle photos and policy wording into a structured, reviewable claim draft.**

[Open the app](https://vehicle-damage-vision.vercel.app)

The app assesses visible damage, prepares an indicative repair estimate, and drafts a policy-evidence-linked explanation. It does not decide coverage, approve claims, or replace an insurer, repair professional, or human reviewer.

## Role completion

| Role | Workstream | Status |
|---|---|---|
| 1 | Vehicle vision and evaluation | Complete |
| 2 | Repair-cost engine | Complete |
| 3 | Policy retrieval and claim drafting | Complete |

These roles are marked complete per the project lead's confirmation. The evaluation, pricing, and human-review caveats below remain part of the project's documented limitations; role completion does not turn them into verified results.

## How it works

1. Add vehicle and incident details, photos, and a policy wording PDF.
2. The vision pipeline returns a structured damage assessment; the cost engine estimates repairs from available price and rate data.
3. Policy retrieval uses the PDF supplied for that request to prepare a cited claim explanation.
4. Review the assessment, estimate, and citations before using or sharing the draft.

The output uses the project's [Contract A, B, and C schemas](schemas/). The language model does not recalculate the structured repair estimate.

## Try it

The app is hosted on Vercel and has no login or access password. Anyone with the URL can submit a request and use the deployment's Gemini quota. Do not upload personal or claim-sensitive documents unless you have permission and accept the processing described in the consent prompt. Use Vercel Deployment Protection if access should be restricted.

The app does not save uploads. Photos, claim details, and retrieved policy excerpts are sent to Google Gemini only after consent. The policy PDF must contain extractable text; scanned PDFs need OCR. The app does not verify that the uploaded PDF matches the insurer or UIN entered, and its policy citations and estimates need human review.

## Run locally

Use Python 3.12, matching the Vercel runtime. Create `.env` from [`.env.example`](.env.example), then set the credentials you need:

```dotenv
GEMINI_API_KEY=your-key
GEMINI_MODEL=your-supported-gemini-model
GROQ_API_KEY=your-key
```

Never commit `.env` or real credentials.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m uvicorn app:app --reload
```

Open `http://127.0.0.1:8000`. The app accepts up to five JPEG, PNG, or WebP photos and one text-based PDF up to 2.5 MB and 300 pages. The full request must fit Vercel's 4 MB limit; photos are resized in the browser. `GEMINI_API_KEY` and `GEMINI_MODEL` are required for the integrated app. `GROQ_API_KEY` is used by Groq vision/evaluation runs.

The standalone photo demo is available with:

```powershell
python -m streamlit run src/vision/demo_app.py
```

## Deploy on Vercel

Set `GEMINI_API_KEY` and `GEMINI_MODEL` in the Vercel project environment, then deploy:

```powershell
vercel
vercel --prod
```

`/api/health` reports whether the required settings are present; it does not verify that Gemini accepts the key. A successful claim submission is the end-to-end credential check.

## Dependency security

The RAG workflow uses BGE embeddings, exact NumPy cosine similarity, and BM25. ChromaDB has been removed from the local and development dependencies; vector caches are stored as NumPy archives and loaded with pickle disabled. The Vercel claim path does not use this local cache.

## Evaluation

The table below is rounded from [`eval/results/summary_with_ci.csv`](eval/results/summary_with_ci.csv). These are exploratory results on a small image set, not evidence that a model is generally better for insurance claims. Confidence intervals are 95% image-level bootstrap intervals.

| Model / prompt | Images | Damage-type F1 (95% CI) | Part exact (95% CI) | First-try JSON | Avg. retries | Latency (s) | Avg. tokens in/out | Cost (USD/image) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Gemini / v0 baseline | 20 | .781 (.688–.871) | .450 (.250–.700) | 0% | 1.00 | 4.900 | 1,588 / 285 | .001189 |
| Gemini / v1 structured | 20 | .800 (.691–.892) | .650 (.450–.850) | 100% | 0.00 | 3.702 | 1,705 / 194 | .000996 |
| Gemini / v1 + schema | 20 | .831 (.712–.931) | .550 (.350–.750) | 100% | 0.00 | 2.019 | 1,705 / 189 | .000983 |
| Gemini / v2 few-shot | 20 | .750 (.612–.871) | .700 (.500–.900) | 100% | 0.00 | 2.735 | 4,130 / 207 | .001756 |
| Gemini / v3 CoT | 20 | .781 (.656–.893) | .600 (.400–.800) | 95% | 0.05 | 2.350 | 1,961 / 360 | .001489 |
| Gemini / v4 best (extra) | 20 | .925 (.866–.984) | .700 (.500–.900) | 90% | 0.10 | 3.328 | 4,979 / 378 | .002439 |
| Qwen/Groq / v0 baseline (extra) | 20 | .658 (.535–.753) | .300 (.100–.500) | 0% | 1.05 | 35.591 | 2,576 / 747 | .005048 |
| Qwen/Groq / v1 structured | 20 | .763 (.595–.891) | .450 (.250–.651) | 90% | 0.10 | 24.787 | 2,408 / 302 | .003133 |
| Qwen/Groq / v1 + schema | 20 | .593 (.367–.772) | .400 (.200–.650) | 90% | 0.00 | 21.268 | 2,070 / 108 | .002086 |
| Qwen/Groq / v2 few-shot | 20 | .730 (.581–.850) | .400 (.200–.600) | 100% | 0.00 | 47.335 | 5,633 / 241 | .005469 |
| Qwen/Groq / v3 CoT | 20 | .761 (.653–.849) | .350 (.150–.550) | 85% | 0.10 | 30.993 | 2,524 / 500 | .004018 |

### What the results do not establish

- The scored evaluation uses 20 images. The 10 dev-image labels, including the few-shot examples, are unverified.
- The v4 prompt was selected after inspecting the same scored images, so its score is optimistic. Left/right part confusion remains a known failure mode.
- Some Qwen/Groq runs contain provider-error outputs; inspect the per-image results before interpreting their scores.
- Pricing data is incomplete: some parts or labour/paint rates remain unpriced, and the available garage quote contains assumptions that still need confirmation. See the [pricing audit](data/prices/DATA_QUALITY_AUDIT.md).
- The policy groundedness worksheet has 186 statements awaiting human review across five distinct Contract A/B pairs. The insurer assignments are synthetic; they are not five verified insurer-linked claims. See the [groundedness report](docs/role3/groundedness_evaluation_report.md).

## Team

This was a team project led primarily by **Aarti Panchal**, who carried the bulk of the implementation and integration: the vision pipeline and evaluation, the end-to-end app, and its Vercel deployment. **Jyothika-aiml** contributed the deterministic cost engine and its tests. **Nakshathira B** contributed policy-document collection, retrieval, claim writing, and the related evaluation. These credits reflect code, commits, and project reports in the repository; they do not imply equal workload or hours.

## Development

Run the test suite and lint checks from the repository root:

```powershell
python -m pytest -q
ruff check --line-length 120 src/vision eval scripts tests
python -m scripts.export_contract_schema --check
```

Useful references: [vision results](docs/role1/RESULTS.md), [cost-engine handoff](docs/role2/ROLE2_HANDOFF_STATUS.md), [policy-draft report](docs/role3/REPORT.md), and [dataset instructions](data/cardd_eval/README.md).
