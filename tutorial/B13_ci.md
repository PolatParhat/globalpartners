# Stage B13: continuous integration

**Goal:** every push runs the tests on a clean machine. Prerequisites: A13, B3, B12.

## Steps

1. Push your rebuild to a private GitHub repo: `gh repo create globalpartners-rebuild --private --source . --push`.
2. `tests/requirements.txt`: pytest, pyspark (matching Glue 5.1: Spark 3.5.6), pandas, pyyaml, streamlit, plotly, boto3.
3. `.github/workflows/ci.yml`:
   - triggers: `push` and `pull_request` to `main`; `permissions: contents: read`
   - job `unit-tests` on `ubuntu-24.04`: checkout → `setup-python` 3.11 with pip cache → `setup-java` 17 (Spark needs the JVM) → `pip install -r tests/requirements.txt` → `python -m py_compile dags/*.py` → `pytest`
   - `timeout-minutes: 15`
4. Open a PR from a branch; watch the check; break a test on purpose and watch it fail; fix.
5. Add the `infra` job after B14.

## Check

- A PR shows a green `unit-tests` check.
- A deliberately broken test shows red with a readable log.

## Compare with the real project

`.github/workflows/ci.yml` (two jobs, versions pinned to match Glue 5.1).

## Done when

CI is green on your PR and red when you break a test.
