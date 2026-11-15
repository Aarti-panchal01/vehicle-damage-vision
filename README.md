# Vehicle Damage Vision - Role 1

This repository contains Role 1's vision module and prompt evaluation for the Vehicle Damage Claim Generator. It accepts car photos, vehicle details, and an incident description, then returns a validated Contract A damage report or a structured error. It does not estimate repair prices or decide repair versus replacement.

## Where it fits

The project has four roles. Role 1 turns claim photos and user-provided vehicle details into Contract A for the downstream cost, policy/RAG, and application roles. Contract A is defined in [`schemas/contract_a.schema.json`](schemas/contract_a.schema.json); the field-by-field handoff is in [`docs/role1/OUTPUT_CONTRACT.md`](docs/role1/OUTPUT_CONTRACT.md).

## Quick start

From the repository root, create and activate a virtual environment, then install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create a local, ignored `.env` file and set `GEMINI_API_KEY` and/or `GROQ_API_KEY`. The example file contains blank values only. A free Gemini API key can be created in [Google AI Studio](https://aistudio.google.com/app/apikey). Keep real keys local; never commit them. For the offline demo, select the mock provider in `src/vision/demo_app.py`.

Python 3.9.6 compatibility has not been runtime-tested; see Known issues.
The default `v4_best` adapter prompt and few-shot prompts require local `dev_03.jpg` and `dev_10.jpg` files; the dataset images are not bundled. Rebuild them using the command in Known issues before using those prompts.

## Calling the module

For files on disk, `load_image` takes a **file path**:

```python
from src.vision import assess_damage, load_image, make_provider

result = assess_damage(
    images=[load_image("car.jpg")],
    vehicle={"make": "Maruti Suzuki", "model": "Swift", "year": 2021, "fuel": "petrol"},
    provider=make_provider("gemini"),
    user_description="Scraped a parking pillar while turning out of the basement",
    claim_id="CLM-20261020-001",
)
if result.ok:
    contract_a = result.report.model_dump()
else:
    error = result.error.model_dump()
```

For upload bytes, use `run_vision` from [`src/vision/adapter.py`](src/vision/adapter.py). It builds `ImageInput` objects and always returns either a Contract A dictionary or a `VisionError` dictionary; it does not raise ordinary exceptions to the caller:

```python
from src.vision.adapter import run_vision

result = run_vision(
    photo_bytes_list=[uploaded_bytes],
    vehicle={"make": "Maruti Suzuki", "model": "Swift", "year": 2021, "fuel": "petrol"},
    description="Scraped a parking pillar while turning out of the basement",
    claim_id="CLM-20261020-001",
)
if "error_code" not in result:
    contract_a = result
else:
    error = result
```

The default adapter configuration uses Gemini and the default prompt. To run the demo from the repository root:

```powershell
python -m streamlit run src/vision/demo_app.py
```

## Using this from the team repository

Either copy this repository's `src/vision` folder and the required entries from `requirements.txt` into the team repository, or clone this repository next to the team repository and make it importable. Imports use `src.vision`, so run from a repository root that contains the `src` package. Do not copy `.env`; configure keys locally in the team repository.

## Contract A summary

A success report contains `claim_id`, user-supplied `vehicle`, `user_description`, a list of validated `damages`, `image_quality_flags`, `model_used`, and `prompt_strategy`. A damage entry includes the allowed part, damage type, severity, confidence, image index, and notes. A failure is a structured `VisionError`; see [`docs/role1/OUTPUT_CONTRACT.md`](docs/role1/OUTPUT_CONTRACT.md) for exact fields, allowed values, and examples.

## Evaluation summary

The following results table and limitations are copied from [`docs/role1/RESULTS.md`](docs/role1/RESULTS.md). The eval set is small; use the limitations when presenting results.


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
| Qwen/Groq / v3 CoT | 20 | .761 (.653–.849) | .350 (.150–.550) | 85% | 0.10 | 30.993 | 2,524 / 500 | .004018 |
| Qwen/Groq / v2 few-shot | 6/20, partial | not run yet | not run yet | not run yet | not run yet | not run yet | not run yet | not run yet |

## Limitations

- The eval set is only 20 images; the plan discussed a larger set, but that has not been run.
- v4 was selected after inspecting the same eval set used for its score.
- Qwen v2 is incomplete at 6/20; the other three planned Qwen configurations completed 20-image passes. Qwen v1 + schema and v3 include provider-error outputs.
- All 10 dev labels are unverified, including both few-shot examples. The 20 eval labels are marked `aarti_verified`.
- The dev check is small and uses unverified labels. Confidence intervals are wide and overlapping; they do not establish generalization.
- Qwen v4 is an extra, not-run configuration.

## Known issues

- Left/right part labels are still sometimes reversed; the evaluation records this as a failure mode.
- The scored eval set has only 20 images. Gemini v4 was selected after reviewing that same eval set, so its score is optimistic.
- Qwen v2 is partial at 6/20 images after Groq quota exhaustion. Resume with `python -m eval.run_eval --configs groq_v2`; cached results are reused.
- Python 3.9.6 has not been tested; no Python 3.9 interpreter was available during this handoff.
- The default `v4_best` adapter prompt and few-shot prompts require the local `dev_03.jpg` and `dev_10.jpg` example images. Without them, the request returns a structured error; rebuild the dataset before using these prompts.
- Dataset images are intentionally not included. To rebuild them, place the source datasets where the builder can access them, configure Kaggle access as described by Kaggle, then run from the repo root:

  ```powershell
  python scripts/build_dataset.py --raw-dir ..\vehicle-claim-genai-raw
  ```

  See [`data/cardd_eval/README.md`](data/cardd_eval/README.md) for dataset sources, licensing, and rebuild details. The labels file is included; the image directory is ignored and must be generated locally.

## Tests

```powershell
python -m pytest -q
ruff check
```

The vision tests use mock providers and do not need an API call.

## Folder structure

```text
src/vision/                 vision pipeline, providers, prompts, schema, byte adapter
tests/                      focused vision tests
docs/role1/                 plan, contract, results, report, demo handoff
prompts/vision/              prompt versions and few-shot examples
mocks/                      success and error examples
schemas/                    Contract A JSON Schema
scripts/                    dataset builder and schema/mock helpers
eval/                       runner, metrics, and eval/results artifacts
data/cardd_eval/            labels and dataset README; images are not included
```
