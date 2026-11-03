# Chapter C1: repository safety

**Branch:** `harden-repo-safety`. **Cost:** free. **Why:** today "never push to main" is a habit; production makes it a rule the platform enforces.

## What you build

1. **Branch protection on `main`** (GitHub → Settings → Branches → rule for `main`; or Rulesets): require a pull request, require the status checks `unit-tests` and `infra` to pass, require branches to be up to date, block force pushes and deletions, require conversation resolution. (Optional: require 1 approval; on a solo repo you may use an admin bypass for yourself.) *You change the setting; Claude explains each option.*
2. **`CODEOWNERS`** (`.github/CODEOWNERS`): `* @your-github-login` plus `/infra/ @your-github-login`, `/config/ @your-github-login`; with protection on, owners are auto-requested for review.
3. **PR template** (`.github/pull_request_template.md`): What/why, how tested, risk, rollback, checklist (tests added, docs updated, no secrets).
4. **Release tags:** `git tag -a v1.0.0 -m "Project closed: deployed, verified, deleted" && git push --tags`; a short `CHANGELOG.md`.
5. **Commit hygiene:** conventional-ish messages ("Fix MWAA log level: …"); optional signed commits.

## Check

- Try `git push origin main` from a clone: it must be **rejected**.
- Open a PR with a failing test: the merge button is blocked until CI is green.

## Interview angle

"How do you protect production code?": required reviews, required CI, no direct pushes, CODEOWNERS for sensitive paths, tags for releases, audit log.

## Done when

A direct push to main fails, and a red CI blocks the merge.
