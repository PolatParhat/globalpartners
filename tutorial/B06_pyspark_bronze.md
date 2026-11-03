# Stage B6: PySpark and the bronze layer (incremental extract)

**Goal:** a job that copies new and changed rows from SQL Server into Iceberg bronze tables, with a watermark and a 3-day lookback. Prerequisites: A7, A8, B5.

## Concepts you apply

Incremental load, watermark, lookback, append-only bronze with audit columns, JDBC reads, Iceberg tables, idempotent reruns. (Chapters A3, A7, A8.)

## Steps

1. **Spark container:** add a `spark` service built from the AWS Glue 5.1 image (the same Spark, Python and Iceberg as AWS Glue) with the project folder mounted, `PIPELINE_ENV=local`, and the Iceberg catalog `lake` configured (Hadoop catalog in a local folder) via `common/spark.py` `build_spark()`.
2. **`common/job_args.py`:** parse `--batch-id` (and others) the same way locally and on AWS (Glue passes `--KEY value`).
3. **`common/source.py`:** `read_source(spark, db, table, where=None)` using `spark.read.format("jdbc")` with the `etl_reader` login. Credentials come from environment variables (local) or Secrets Manager (AWS), never hard-coded.
4. **`common/tables.py`:** helpers for table names (`lake.bronze.order_items`) and `merge_into` (used from B7).
5. **`common/run_log.py`:** `logged_run(...)` context manager that writes a row to `lake.ops.pipeline_runs` (start, end, rows, status, batch id) even when the job fails.
6. **`jobs/extract_to_bronze.py`:**
   - read the watermark from `lake.ops.watermarks` (none on the first run → read everything),
   - read `order_items` where `creation_time_utc > watermark − 3 days`; read the options of those orders (options have no timestamp of their own); read all of `date_dim`,
   - add audit columns `_batch_id` and `_loaded_at`, **append** to bronze,
   - advance the watermark **only after every table is written**.
7. **Tests:** pure helpers (watermark window calculation) get unit tests.

```bash
docker compose exec spark spark-submit src/globalpartners/jobs/extract_to_bronze.py --batch-id manual-1
```

## Check

- After replay days 1 to 3: bronze `order_items` has **463 lines**, options **429**.
- Run the job again and look at the counts. Because bronze is append-only and the job re-reads the last 3 days, expect bronze to hold repeated copies of recent rows (check `_batch_id`); silver (B7) must not duplicate them. That is the design: bronze is raw history, MERGE downstream makes reruns safe. (Verify this against the real job's behavior and note what you see.)
- Break the run (kill it mid-way): the watermark must not move.

```sql
SELECT count(*) FROM lake.bronze.order_items;
SELECT * FROM lake.ops.watermarks;
SELECT * FROM lake.ops.pipeline_runs ORDER BY started_at DESC LIMIT 5;
```

## Compare with the real project

`src/globalpartners/jobs/extract_to_bronze.py`, `common/source.py`, `common/spark.py`, `common/run_log.py`, `common/tables.py`.

## Done when

Reruns are safe, the watermark only moves on success, and you can explain every line of the job.
