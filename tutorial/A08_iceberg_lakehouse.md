# Chapter A8: Apache Iceberg and the lakehouse

**Time:** 1 to 2 sessions. **Goal:** explain what a table format adds to Parquet files, use MERGE and time travel, and answer lakehouse interview questions.

## 1. The problem

A data lake is just files in S3. Files alone have no transactions: a job that dies halfway leaves half-written data; two writers collide; you cannot update one row; you cannot see yesterday's version; listing millions of files is slow.

## 2. What a table format is

A **table format** is metadata kept next to the Parquet files that says "this table = these files, at this version, with this schema". Iceberg, Delta Lake and Hudi are the three main ones. Iceberg's layers:

```
catalog  →  metadata file (schema, partition spec, snapshots)  →  manifest list  →  manifests  →  data files (Parquet)
```

- **Catalog:** where the pointer to the current metadata file lives (here: **AWS Glue Data Catalog** in prod, a **Hadoop** catalog in local files). Tables are addressed `lake.<layer>.<table>`, e.g. `lake.gold.fact_order`.
- **Snapshot:** the table's state after one commit. Every write creates a new snapshot; old ones stay until expired.
- **Manifest:** a list of data files with per-file column statistics (min/max, null counts) used to skip files.
- **Atomic commit:** the catalog pointer switches to the new metadata in one step. Readers see the old or the new snapshot, never half.

## 3. What you get

| Feature | How it helps this project |
|---|---|
| **ACID transactions** | a failed job leaves no half-written table |
| **MERGE / UPDATE / DELETE** | silver and gold are upserted by key: reruns never duplicate (the failure-reload requirement) |
| **Time travel** | read the table as of a snapshot or timestamp; roll back a bad load |
| **Schema evolution** | add/rename/drop columns without rewriting data |
| **Hidden partitioning** | partition by `days(ts)` and queries filter on `ts` normally |
| **Partition/file pruning** | statistics skip files that cannot match |
| **Engine independence** | Spark writes, Athena reads |

## 4. Try it (in the project's Spark container)

Use the lake SQL prompt from `STATUS.md` ("Lake SQL prompt"), then:

```sql
SELECT count(*) FROM lake.gold.fact_order;
SELECT * FROM lake.gold.fact_order.snapshots;        -- one row per commit
SELECT * FROM lake.gold.fact_order.history;
SELECT * FROM lake.gold.fact_order.files LIMIT 5;    -- the Parquet files and their stats
```

Time travel:

```sql
SELECT count(*) FROM lake.gold.fact_order VERSION AS OF <snapshot_id>;
SELECT count(*) FROM lake.gold.fact_order TIMESTAMP AS OF '2026-11-01 12:00:00';
```

Rollback (changes the table, so practice on a copy of the lake):

```sql
CALL lake.system.rollback_to_snapshot('gold.fact_order', <snapshot_id>);
```

## 5. MERGE in Iceberg

```sql
MERGE INTO lake.silver.order_items t
USING updates s ON t.order_id = s.order_id AND t.line_id = s.line_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;
```

Rules: the source must be unique per key; the match key must be the business key; `UPDATE SET *` copies all columns. In this project every load re-reads a 3-day lookback; MERGE makes that safe.

## 6. Maintenance (production chapter C6)

Every small write creates small files and a snapshot. Without care, tables slow down.
- `CALL lake.system.rewrite_data_files('gold.fact_order')` compacts small files.
- `CALL lake.system.expire_snapshots(table => 'gold.fact_order', older_than => TIMESTAMP '…')` removes old snapshots (and with it, the ability to time-travel before them).
- `CALL lake.system.remove_orphan_files(…)` deletes files no snapshot references.
- Write mode: copy-on-write (rewrite files on update; fast reads) vs merge-on-read (write delete files; fast writes).

## 7. Compared with others

| | Iceberg | Delta Lake | Hudi |
|---|---|---|---|
| Origin | Netflix | Databricks | Uber |
| Engine support | very broad (Spark, Trino, Athena, Flink) | strongest on Spark/Databricks | Spark/Flink |
| Strength here | native in Athena + Glue | | |

Lakehouse vs warehouse: the lakehouse keeps data in open files on cheap storage with warehouse-like features; a warehouse (Snowflake, Redshift) bundles storage and compute.

## 8. Exercises

1. Run the four metadata queries above on a gold table; explain each column of `snapshots`.
2. Count `fact_order` at an earlier snapshot and now; explain the difference.
3. On a copy of the lake, delete a few rows, then roll back and prove the count returns.
4. Explain why a rerun of `bronze_to_silver` for the same day does not change silver (MERGE).
5. Find where the code calls MERGE: `grep -rn "MERGE" src/`.

## Interview questions

1. Why Iceberg and not plain Parquet? 2. What is a snapshot; how does time travel work? 3. How does Iceberg get atomic commits on S3 (which has no rename)? (pointer swap in the catalog, optimistic concurrency) 4. Copy-on-write vs merge-on-read? 5. What is hidden partitioning? 6. How do you handle schema changes? 7. What is the small-files problem and how does compaction fix it? 8. Iceberg vs Delta vs Hudi? 9. What are manifests for? (file-level statistics for pruning) 10. How do you roll back a bad load?

## Done when

Exercises 1 to 5 done; you explain the catalog → metadata → manifest → data file chain from memory.
