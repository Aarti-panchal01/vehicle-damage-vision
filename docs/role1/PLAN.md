# Role 1 plan: vision + prompting

Source of truth: `Vehicle_Damage_Claim_Team_Plan.docx` (team plan, Oct 7 2026) and the course guidelines for UE24AM343AB5, Project 10. Where the Role 1 task brief and the team plan disagree, the team plan wins; every such case is listed in [DECISIONS.md](DECISIONS.md).

## What Role 1 owns (team plan, section 5)

Photos + user description + vehicle details in, **Contract A** out, plus the prompt evaluation that becomes the main results section of the report. Folders: `src/vision/`, `data/cardd_eval/`, `eval/`.

## What I found in Phase 0

- No GitHub repo existed yet under `Aarti-panchal01` or anywhere searchable as `vehicle-claim-genai`. The team plan says Role 4 creates it by Oct 10. I built this branch in a local repo laid out exactly like the team plan's folder structure, so it can be pushed onto Role 4's repo when it exists.
- No teammate code exists yet, so nothing could be duplicated or broken. Shared files I had to create are listed in the PR description.
- My role in the team plan matches the brief ("vision + prompting"). Differences in detail: Contract A's exact fields, the 6 CarDD damage types, 2 models instead of 1, and a max of 2 repair retries.

## Build order

1. **Dataset** (`data/cardd_eval/`): 30 images (20 eval, 10 dev) from the CarDD test split plus 4 undamaged photos, with draft part and severity labels. Build script instead of manual copying.
2. **Contract A + vocabularies** (`src/vision/schema.py`, `schemas/contract_a.schema.json`): Pydantic models, strict JSON Schema for API-side enforcement.
3. **Providers** (`src/vision/providers/`): Gemini (google-genai) and Groq (Qwen 3.8 27B, the open VLM), a mock for tests, and a disk cache.
4. **Pipeline** (`src/vision/assess.py`): prompt -> model -> parse/validate -> text-only repair (max 2 retries) -> merge across photos -> Contract A or a structured `VisionError`.
5. **Prompts** (`prompts/vision/`): v0 baseline, v1 structured, v2 few-shot, v3 chain-of-thought, then v4 written only after reading v1-v3 failures. Old versions are never edited.
6. **Evaluation** (`eval/`): every prompt on both models, plus v1 with API schema enforcement, on the 20 eval images. Cached replies, CSV + charts, RESULTS.md written only from those numbers.
7. **Demo** (`app_role1.py`): Streamlit page for upload, prompt choice, JSON + readable summary.
8. **CI + docs + PR**: lint + mocked unit tests in GitHub Actions; OUTPUT_CONTRACT.md for Roles 2-4; REPORT.md for Aarti.

## Assumptions

- Gemini "Flash tier" means a current Gemini Flash model on the free AI Studio key. The newest (3.8 Flash) was returning 503 "high demand" on Oct 8, so the default is `gemini-3.5-flash` (see DECISIONS).
- The open VLM is `qwen/qwen3.8-27b` on Groq, the only vision model Groq lists today.
- 20 eval images are enough for Review 2 ("first version of all 4 prompts, tested on 20 images"). The 200-300 image run planned for Review 3 reuses the same code with a bigger labels file.
- Labels drafted by Claude are good enough to compare prompts against each other, but every one must be checked by hand before numbers go in the report.
