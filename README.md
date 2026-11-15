# Vehicle Damage Claim Generator

[![Project CI](https://github.com/Aarti-panchal01/vehicle-damage-vision/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Aarti-panchal01/vehicle-damage-vision/actions/workflows/ci.yml)

This is the shared project repository for a four-person team building a vehicle-damage claim workflow. It accepts vehicle photos and claim context, produces a validated damage report, and provides an integration point for the team's remaining claim-processing components. The checked-in implementation currently contains the vision and prompting pipeline, its Contract A interface, and evaluation artifacts; teammate modules are being integrated here.

## Project flow

```text
Vehicle photos + claim details
              |
              v
Vision damage assessment -> Contract A -> claim-processing components -> reviewed claim
```

The vision component reports visible exterior damage only. It does not infer hidden damage, estimate repair prices, or determine policy coverage. Those outputs must come from the corresponding team components.

## What is in this repository

- **Vision pipeline** (`src/vision/`): image handling, Gemini and Qwen/Groq providers, versioned prompts, output validation, bounded repair retries, damage merging, and a byte-oriented adapter.
- **Contract A** (`schemas/contract_a.schema.json`, `src/vision/schema.py`): the machine-readable handoff between the vision component and the rest of the application.
- **Prompt evaluation** (`eval/`): cached evaluation records, metrics, charts, and the evaluation runner.
- **Examples and fixtures** (`mocks/`): Contract A and structured error examples.
- **Team documents** (`docs/`): project plan, interface notes, evaluation findings, and report input.

See [`docs/role1/OUTPUT_CONTRACT.md`](docs/role1/OUTPUT_CONTRACT.md) for the existing interface details and [`docs/role1/RESULTS.md`](docs/role1/RESULTS.md) for the full evaluation and limitations.

## Quick start

Use Python 3.13 or a compatible version supported by the pinned packages. Python 3.9.6 has not been runtime-tested.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -r requirements-dev.txt
```

Create a local `.env` file and configure `GEMINI_API_KEY` and/or `GROQ_API_KEY` for live providers. Do not commit credentials. A Gemini key can be created in [Google AI Studio](https://aistudio.google.com/app/apikey). The `.env.example` contains blank values.

The few-shot prompts, including the default `v4_best` adapter prompt, use local `dev_03.jpg` and `dev_10.jpg` images. Images are not included in this repository. Rebuild the permitted dataset files as described in [`data/cardd_eval/README.md`](data/cardd_eval/README.md) before using those prompts.

## Use the vision interface

For uploaded photo bytes, use the adapter. It returns either a Contract A dictionary or a `VisionError` dictionary:

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

For photos on disk, `load_image` accepts a file path and `assess_damage` returns an assessment result object. See [`src/vision/__init__.py`](src/vision/__init__.py) and [`docs/role1/OUTPUT_CONTRACT.md`](docs/role1/OUTPUT_CONTRACT.md).

Run the demo from the repository root:

```powershell
python -m streamlit run src/vision/demo_app.py
```

## Evaluation snapshot

The table below is copied from [`docs/role1/RESULTS.md`](docs/role1/RESULTS.md). Scores are exploratory, not a claim of general model superiority.

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

### Limitations

- The scored evaluation set contains 20 images; a larger set has not been run.
- The v4 prompt was selected after inspecting the same evaluation set, so its score is optimistic.
- Qwen v2 is partial at 6/20 after quota exhaustion. Qwen v1 + schema and v3 include provider-error outputs.
- All 10 dev labels are unverified. The 20 eval labels are marked `aarti_verified`.
- Left/right part confusion remains a failure mode. Dataset images are not distributed with this repository.

## Contributing

This is the shared repository for the team. Add your component in a focused branch, document its interface, include tests, and open a pull request against `main`. Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before changing shared contracts or evaluation data.

## Repository layout

```text
src/vision/                 image-to-Contract-A pipeline and providers
tests/                      automated unit tests
prompts/vision/             versioned prompt templates and examples
schemas/                    shared JSON Schema
mocks/                      interface examples
eval/                       runner, metrics, charts, and result records
data/cardd_eval/            labels and data notes; images are not included
docs/role1/                 existing interface, evaluation, and report notes
scripts/                    dataset builder and schema/mock helpers
```

## Team

The repository is owned by Aarti Panchal (`@Aarti-panchal01`). Team collaborators are `@gaganaraj`, `@nakshathira200-svg`, and `@jyothika-aiml`. Please document each person's actual contributions in the final report rather than inferring them from repository access.
