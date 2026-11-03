# Chapter C6: Iceberg table maintenance

**Branch:** `harden-maintenance`. **Cost:** a few Glue seconds per run. **Prerequisite:** chapter A8.

## Why

Each load writes new small files and a new snapshot. Over months: many tiny files (slow reads, S3 request costs), a long snapshot history (large metadata), and orphan files left by failed jobs.

## What you build

A new Glue job / local job `table_maintenance.py` (scheduled weekly by its own DAG `globalpartners_maintenance`), with parameters for the age to keep:

1. **Compaction:** `CALL lake.system.rewrite_data_files(table => 'gold.customer_daily_snapshot', options => map('target-file-size-bytes','134217728'))` for every table (start with the snapshot table, the biggest).
2. **Snapshot expiry:** `CALL lake.system.expire_snapshots(table => '…', older_than => <now − 30 days>, retain_last => 5)`. Remember: expiring snapshots removes the ability to time-travel before them. Choose retention deliberately (and document it).
3. **Orphan files:** `CALL lake.system.remove_orphan_files(table => '…', older_than => <now − 3 days>)` (the age guard avoids deleting files of in-flight writes).
4. **Manifest rewrite:** `rewrite_manifests` when planning gets slow.
5. **Table properties:** `write.target-file-size-bytes`, `write.metadata.delete-after-commit.enabled`, `write.metadata.previous-versions-max`.
6. **Log what it did** to `ops.pipeline_runs` (files before/after).

## Check (local lake)

- Count data files before and after compaction (`SELECT count(*) FROM lake.gold.<t>.files`); row counts unchanged.
- After expiry, an old snapshot id no longer works for time travel; the current table is unchanged.
- Run twice: no change the second time (idempotent).

## Interview angle

Small-files problem, compaction, snapshot retention trade-offs (storage vs recovery), orphan files, partition evolution.

## Done when

The job runs in the local DAG, results are logged, and you can state the retention policy and its reason.
