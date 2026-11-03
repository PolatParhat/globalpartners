# Chapter C10: governance and scale

**Branch:** `harden-governance`. **Cost:** mostly design and documentation; Lake Formation itself is free, scale tests cost Glue time.

## Governance

1. **Data catalog and dictionary:** `docs/data_dictionary.md` generated from the table definitions: table, grain, owner, description, each column (type, meaning, PII yes/no, source). Add Glue table/column comments in the code so the catalog shows them. A test fails if a gold column has no description.
2. **Lake Formation (or IAM-scoped access):** register the lake location, grant column- and table-level permissions to roles (analysts read gold only; no one but the pipeline reads bronze/silver), tag PII columns and hide them from non-privileged roles.
3. **PII handling:** inventory (`printed_card_number`, `user_id`); keep card numbers in silver only (already true); mask/hash in any export; define access reasons.
4. **Retention:** per layer (bronze 13 months, silver 25 months, gold per policy), implemented with S3 lifecycle + Iceberg expiry; document the legal/business reason.
5. **Deletion on request (right to be forgotten):** a procedure to delete a customer from silver and gold (Iceberg `DELETE`), rebuild snapshots, expire old snapshots so the data is physically gone; and the limitation that bronze must also be handled.
6. **Lineage:** the batch id on every row plus `ops.pipeline_runs` gives run-level lineage; optionally publish OpenLineage events.
7. **Data contracts:** a schema + expectations file for the source tables, validated in `extract_to_bronze` (ties to C4 drift).

## Scale and performance

8. **Partitioning:** Iceberg hidden partitioning by `days(business_date)` on facts and `days(snapshot_date)` on the snapshot; test query plans for file pruning.
9. **Sizing test:** generate 10× and 100× synthetic data (replicate with new keys); run the pipeline; record job times, shuffle sizes, Glue DPU-hours and cost per run; find the first bottleneck (the snapshot window functions; JDBC single-thread reads, so add `partitionColumn` and `numPartitions`).
10. **JDBC parallel reads and incremental correctness at scale;** AQE on; broadcast thresholds; skew checks for the guest (NULL) key.
11. **Cost per run** reported in `ops.pipeline_runs`.

## Check

- The dictionary test passes; a masked role cannot see PII columns in Athena; a deletion request removes a test customer everywhere (verified with queries); a 10× run completes with recorded times.

## Interview angle

Data governance, catalog, lineage, PII/GDPR, retention, column-level security, partitioning strategy, capacity planning, cost-performance trade-offs.

## Done when

The dictionary, the retention policy, the deletion procedure and a scale report with numbers are in `docs/`.
