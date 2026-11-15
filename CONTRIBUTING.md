# Contributing

This is the shared repository for the vehicle damage claim project. Keep contributions scoped to the component you are implementing and coordinate changes to shared interfaces before merging.

## Workflow

1. Start from an up-to-date `main` branch and create a feature branch.
2. Keep commits focused and describe the user-visible change.
3. Add or update tests for behavior you change.
4. Update the README or component documentation when the interface or setup changes.
5. Open a pull request to `main` and include the test and lint results.

## Project safeguards

- Never commit `.env` files, API keys, access tokens, or other credentials.
- Do not commit the underlying CarDD/Kaggle images. Follow the terms in `data/cardd_eval/README.md`.
- Do not change Contract A or its schema without coordinating with every component that consumes it.
- Do not report evaluation numbers unless they are backed by files under `eval/results/` or a recorded run.
- Distinguish implemented components from planned integrations in documentation.

## Local checks

Install both dependency files, then run:

```powershell
python -m pytest -q
ruff check --line-length 120 src/vision eval scripts tests
python -m scripts.export_contract_schema --check
```

The unit tests use mock providers and should not call paid model APIs.
