# Role 1 handoff message

Hi team — Role 1 has the Contract A pipeline, provider adapters, validation/repair flow, prompts, mocks, and evaluation outputs ready for integration. The JSON Schema check passes; the vision tests are included in the repo.

The eight planned model/strategy runs have seven complete 20-image passes. Qwen v2 reached 6/20 and stopped at `eval_07` on Groq quota. To resume tomorrow, run this from the repo root; the first six replies are cached:

```powershell
python -m eval.run_eval --configs groq_v2
```

After it finishes, refresh charts with:

```powershell
python -m eval.make_charts
```

Sample outputs in `mocks/`:

- `contract_a_001_dev_01.json`: front-bumper scratch and dent plus a broken headlamp.
- `contract_a_002_eval_18.json`: no damage, represented by `damages: []`.
- `vision_error_example.json`: `invalid_model_output` after three attempts.

Known integration notes:

- `load_image(path)` reads a disk path. The Streamlit app receives uploaded bytes and constructs `ImageInput` directly; `src/vision/adapter.py` now exposes `run_vision(...)` for byte input.
- The original `assess_damage` can raise for invalid vehicle data or prompt-loading failures rather than returning `VisionError`. The adapter catches these and returns a structured error dict.
- Python 3.9.6 is not installed here, so its environment has not been tested.
- Qwen v1 + schema and v3 completed their 20-image runs, but include provider-error responses; Qwen v2 remains partial. Qwen v4 is an extra configuration and has not been run.
- All 10 dev labels, including the few-shot examples, remain unverified. The 20 eval labels are marked `aarti_verified`.

The demo's current provider/prompt defaults are Gemini and `v4_best`. Since v4 was selected after reviewing the same 20 eval images, its score should be presented as exploratory, not as an unbiased final estimate.
