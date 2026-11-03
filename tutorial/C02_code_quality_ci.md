# Chapter C2: code quality and supply-chain checks in CI

**Branch:** `harden-code-quality`. **Cost:** free.

## What you build

1. **ruff** (lint + format) configured in `pyproject.toml`:

```toml
[tool.ruff]
line-length = 120
target-version = "py311"
[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]      # pycodestyle, pyflakes, import order, bugbear, pyupgrade
```

   Run `ruff check .` and `ruff format --check .`; fix what it finds (the project is pyflakes-clean already).
2. **Type checks (optional step by step):** `mypy src/ --ignore-missing-imports`; start with a lenient config and tighten.
3. **pre-commit:** `.pre-commit-config.yaml` with ruff, trailing whitespace, end-of-file fixer, `check-yaml`, and a secret scanner (`gitleaks`). `pre-commit install` runs them before each commit.
4. **CI job `lint`** in `ci.yml`: install ruff, run check + format check; add it to the required checks (C1).
5. **Dependabot** (`.github/dependabot.yml`): weekly updates for `pip` (root, `tests`, `infra`), `github-actions`, and `docker`.
6. **Secret scanning and push protection:** enable in repo settings (Code security).
7. **Dependency audit:** `pip-audit -r requirements.txt` (and the infra/test requirements) as a CI step or scheduled workflow; triage findings.

## Check

- Introduce an unused import: CI `lint` fails. Remove it: green.
- Try to commit a fake AWS key (`AKIA…` pattern) on a scratch branch: pre-commit or push protection blocks it.

## Interview angle

Shift-left: catch style, bugs, secrets and vulnerable dependencies before review; supply-chain hygiene (pinning, scanning, automatic updates).

## Done when

Lint is a required check, pre-commit runs locally, Dependabot opens its first PR.
