# Chapter C4: observability (freshness, volume, quality alarms)

**Branch:** `harden-observability`. **Cost:** a few cents per month for CloudWatch alarms (only while deployed).

## The questions to answer without opening a console

1. Did today's run finish on time? (**freshness**)
2. Did it load a believable number of rows? (**volume**)
3. Is the quarantine rate normal? (**quality**)
4. Did the schema change? (**drift**)
5. Who gets told, and how fast? (**alerting**)

## What you build

1. **Custom metrics:** the jobs already log to `ops.pipeline_runs` and `ops.dq_results`. Add a small step in `run_log.py` that publishes CloudWatch metrics (`put_metric_data`): `RowsLoaded`, `QuarantineRate`, `DqFailures`, `RunSeconds`, dimensioned by job.
2. **Alarms** (CDK `cloudwatch.Alarm`) wired to the existing SNS topic:
   - freshness: no successful `dq_checks` in 26 hours (alarm on missing data: `treat_missing_data=BREACHING`);
   - volume: `RowsLoaded` far from the 7-day average (a simple threshold first; anomaly detection later);
   - quarantine rate above 1 %;
   - any `DqFailures` > 0.
3. **Schema-drift check:** compare the source's column list to the expected one at the start of `extract_to_bronze`; fail with a clear message when columns are added, removed or retyped.
4. **Dashboard footer:** "data as of <last successful run>" read from `ops.pipeline_runs`.
5. **Tests:** infra tests assert the alarms exist and go to the SNS topic; unit tests for the drift comparison.

## Check

- In a scratch deployment (or by unit test), feed an empty load: the volume alarm condition is met and the DQ check fails.
- Remove a column in a fixture: the drift check names the column.

## Interview angle

Monitoring vs observability; SLIs/SLOs for data (freshness, completeness); alert fatigue (alert on symptoms users feel, not every blip); metrics, logs, traces.

## Done when

Four alarms are defined and tested in CDK, drift detection is unit-tested, and the dashboard shows the data's age.
