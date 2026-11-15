# Role 1 decisions log

Decisions made while building Role 1 without asking, with the reason for each. Where the Role 1 task brief and the team plan disagreed, the team plan was followed.

## Follows the team plan instead of the task brief

| # | Brief said | Team plan says | Done | Why |
|---|---|---|---|---|
| D1 | Output has `vehicle {type, color, visible_side}`, `approx_size_cm`, `image_quality`, `needs_more_photos` | Contract A: vehicle comes from the user form, damages have `image_index` and `notes`, plus `image_quality_flags`, `model_used`, `prompt_strategy` | Contract A exactly | "Do not change a contract without telling the whole group." Size goes in `notes`; `needs_more_photos` can be derived from `image_quality_flags`. Both are listed as proposals in OUTPUT_CONTRACT.md. |
| D2 | Damage types not fixed | 6 CarDD classes | CarDD classes | Lets us score against CarDD labels. |
| D3 | `data/README.md`, `data/labels.json` | Role 1 data lives in `data/cardd_eval/` | `data/cardd_eval/README.md`, `data/cardd_eval/labels.json` | Keeps `data/` free for Roles 2 and 3. |
| D4 | One repair retry | "Maximum 2 retries" | `max_retries=2` by default, configurable | Team plan wins; tests cover both 1 and 2. |
| D5 | v0-v4 on one model | Zero-shot, zero-shot + schema enforcement, few-shot, CoT, on 2 models | Both: v0-v4 prompt files, plus v1 with API schema enforcement, on Gemini and Qwen | Covers the brief's prompt versions and the team plan's 4 strategies x 2 models. Mapping: zero-shot = v1, zero-shot + schema = v1 + `enforce_schema`, few-shot = v2, CoT = v3. |
| D6 | 2 or 3 few-shot examples | 3 example images | 2 examples | Groq accepts at most 3 images per request, and the claim photo is one of them. 2 examples keeps the two models comparable. |
| D7 | 30 images | 200-300 image test split, part labels for ~100 | 30 now | The brief and the Review 2 deliverable ("tested on 20 images") match. The code takes any size labels file for the Review 3 run. |

## Model and API choices

| # | Decision | Why |
|---|---|---|
| D8 | Default Gemini model `gemini-3.5-flash-lite`, not `gemini-3.5-flash` or the newest `gemini-3.8-flash` | On Oct 8, 3.8 Flash returned `503 UNAVAILABLE: high demand` on 4 attempts in a row, and 3.7 Flash took 80-108 s per photo. 3.5 Flash answered in about 3 s but the free tier allows only 20 requests/day on 3.5/3.8 Flash, too few for the eval, so the default became 3.5 Flash-Lite (commit 9c4ba48). All Gemini numbers in `eval/results/` are Flash-Lite. The model name is one argument (`make_provider("gemini", model=...)`), so the run can be repeated on another model later. |
| D9 | Thinking level `low` for Gemini | Keeps latency and thinking-token cost down for every config equally. The CoT effect is then measured from the prompt, not from a hidden reasoning budget. |
| D10 | Open VLM: `qwen/qwen3.8-27b` on Groq, `reasoning_format="hidden"`, default reasoning effort | It is the only vision model on Groq today. At default effort Groq returns no reasoning tokens, so again CoT comes from the prompt. |
| D11 | Schema enforcement uses a hand-written strict JSON Schema (no `$ref`, all fields required, no extra keys) | Groq strict mode requires this shape; Gemini accepts it too, so both models get the same schema. |
| D12 | Repair request is text-only (no photo re-sent) | Format repair does not need the image, and it halves the tokens of a retry. |
| D13 | Keys reused from Aarti's existing local `.env` files (Gemini from Closeli, Groq from Eka) into this repo's git-ignored `.env` | Both keys worked; no new key was needed. `.env` is never committed. |

## Data and labels

| # | Decision | Why |
|---|---|---|
| D14 | CarDD images from the CC BY-NC 4.0 Kaggle mirror | Official CarDD needs a signed form; the mirror allows non-commercial research use. Caveat and citation in `data/cardd_eval/README.md`. |
| D15 | Undamaged cars from a CC0 dataset; bad-quality photos made by degrading clear CarDD photos | CarDD has no undamaged or poor-quality photos. Synthetic degradation means the true damage is known. |
| D16 | Door glass, bus and bare close-up images were dropped | Contract A has no part name for door glass and no way to name a part from a bare close-up. Flagged to the team as a vocabulary gap. |
| D17 | Labels drafted by Claude and marked `claude_draft` | CarDD has no part or severity labels. Every label needs a human check. |
| D18 | Scoring reports both an exact part F1 and a corner-free part F1 | Many CarDD photos are close-ups where the car's left/right or front/rear cannot be read. The corner-free score shows whether a prompt finds the right kind of part even when the side is uncertain. |

## Pipeline behaviour

| # | Decision | Why |
|---|---|---|
| D19 | Merge across photos on (part, damage_type), keeping the higher severity | The team plan says "same part seen twice is kept once, with the higher severity". Merging on part alone would delete a real second damage type (a bumper with a dent and a crack), which Role 2 needs for repair-or-replace. Needs team sign-off. |
| D20 | `image_quality_flags` use the same 0-based index as `image_index` | The team plan example mixes `image_index: 0` and `image_1_blurry`. One numbering for both fields avoids off-by-one bugs downstream. Needs team sign-off. |
| D21 | `prompt_strategy` holds the prompt version id, e.g. `v4_best` or `v1_structured+schema` | Traceable to the exact prompt file. The field is a free string in Contract A. |
| D22 | Failures return a `VisionError` object (codes: `invalid_model_output`, `provider_error`, `quota_exhausted`, `bad_input`) instead of raising | Role 4 can show "please upload clearer photos" without a try/except around every call. |
| D23 | `claim_id` is generated as `CLM-YYYYMMDD-NNN` only when the caller does not pass one | Role 4 should own claim ids; this default is for standalone use. |

## Repo

| # | Decision | Why |
|---|---|---|
| D24 | Built in a local repo with the team plan's folder structure; `main` has only an empty root commit | Role 4 had not created the team repo yet. |
| D25 | `src/vision/` is a package imported as `src.vision`; run commands from the repo root | No packaging or shared config file needed, so no shared file is touched. |
| D26 | CI workflow only watches Role 1 paths | Avoids failing teammates' PRs on Role 1 checks. |
