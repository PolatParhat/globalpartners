# Chapter A7: Spark and PySpark (the interview chapter)

**Time:** 2 to 3 sessions. **Goal:** you can explain how Spark works inside, read a query plan and the Spark UI, fix slow jobs, and answer the common interview questions with examples from this project.
**Versions here:** AWS Glue 5.1 = Spark 3.5.6, Python 3.11, Java 17. Run examples in the project container (see "Setup").

## Setup

Examples use a throwaway session. Run them in the project's Spark container:

```bash
docker compose exec spark python3
```

then at the `>>>` prompt:

```python
from pyspark.sql import SparkSession, functions as F, Window
spark = SparkSession.builder.master("local[2]").appName("learn").config("spark.sql.session.timeZone", "UTC").getOrCreate()
spark.sparkContext.setLogLevel("WARN")
```

`local[2]` means "run Spark inside this one process with 2 worker threads". Real clusters differ only in where the work runs.

---

## 1. What Spark is, in one picture

Spark splits a big job into small tasks and runs them in parallel on many machines (or cores), keeping data in memory where it can.

| Part | Job | In this project |
|---|---|---|
| **Driver** | runs your `main` code, builds the plan, schedules tasks, collects small results | the Glue job's main process |
| **Cluster manager** | hands out machines (YARN, Kubernetes, Standalone, or a managed service) | AWS Glue (2 workers, G.1X) |
| **Executors** | processes on worker machines that run tasks and hold cached data | the Glue workers |
| **Task** | one unit of work on one **partition** of data | |
| **Partition** | a slice of the data; the unit of parallelism | |

**Rule of thumb:** parallelism = number of partitions (up to the number of cores). Too few partitions = idle cores. Too many tiny ones = scheduling overhead.

**Why Spark and not pandas?** pandas runs on one machine and keeps everything in memory; Spark scales out, spills to disk, and reads columnar files lazily. Below a few GB, pandas is simpler and faster. This project uses Spark because the pipeline, the lakehouse (Iceberg) and Glue are built around it, and as the data grows nothing has to be rewritten.

## 2. DataFrames, RDDs, Datasets

| API | What it is | When |
|---|---|---|
| **RDD** | low-level distributed collection of objects, no schema, no optimizer | rarely; legacy and special cases |
| **DataFrame** | distributed table with named, typed columns; goes through the optimizer (Catalyst) | almost always (PySpark) |
| **Dataset** | typed DataFrame (Scala/Java only) | not available in Python |
| **Spark SQL** | the same engine; you write SQL text or DataFrame code, both compile to the same plan | mix freely |

**Interview answer:** "DataFrames carry a schema, so Spark can optimize the plan and use its binary Tungsten format. RDDs are opaque to the optimizer, so DataFrames are faster and clearer."

```python
df = spark.createDataFrame(
    [(1, "boston", 12.50, "done"), (2, "boston", 8.00, "done"), (3, "cambridge", 15.25, "refunded")],
    "order_id int, location string, amount double, status string")
df.printSchema()
df.show()
```

Always give an explicit **schema** (as above) when reading files you do not control. `inferSchema` reads the data twice and guesses (a column of "001" becomes an int). This project's convention: never let Spark guess dates or types (`creation_time_utc` is parsed explicitly, see `transformations/cleaning.py`).

## 3. Transformations, actions and lazy evaluation

- A **transformation** describes a new DataFrame (`select`, `filter`, `withColumn`, `join`, `groupBy…agg`, `orderBy`). Nothing runs.
- An **action** forces the whole chain to run (`show`, `count`, `collect`, `write`, `toPandas`, `take`).

```python
big = spark.range(0, 10_000_000)                     # nothing runs
evens = big.filter(F.col("id") % 2 == 0)             # nothing runs
doubled = evens.withColumn("x2", F.col("id") * 2)    # nothing runs
print(doubled.count())                               # NOW it runs: 5000000
```

**Why lazy?** Spark sees the whole recipe first, so it can reorder (push filters before joins), skip unused columns, and combine steps into one pass. **Consequence:** an error in line 3 can show up when line 9 runs; a DataFrame used twice is computed twice unless cached.

`collect()` and `toPandas()` bring ALL rows to the driver: fine for 100 rows, a crash for 100 million. Use `limit`, `take`, or write to storage.

## 4. Narrow vs wide transformations, shuffles, stages

- **Narrow** (`filter`, `select`, `withColumn`, `map`): each output partition depends on ONE input partition. No data moves between machines. Cheap, pipelined.
- **Wide** (`groupBy`, `join`, `distinct`, `orderBy`, `repartition`, window with partitionBy): output partitions need data from MANY input partitions. Spark must **shuffle**: write data to local disk, send it over the network, and re-group by key. Expensive.

A **job** is started by one action. A job splits into **stages** at each shuffle boundary. A stage is a set of **tasks**, one per partition.

```python
agg = df.groupBy("location").agg(F.sum("amount").alias("revenue"))
agg.explain()
```

Look for `Exchange hashpartitioning(location…)` in the output: that is the shuffle. **Interview:** "Fewer shuffles = faster job. I check `explain()` and the Spark UI for Exchange nodes."

**Shuffle partitions:** after a shuffle, the number of partitions is `spark.sql.shuffle.partitions` (Spark's default is 200; the Glue image used here showed 1000 in the plan above). On small data that is far too many; with **AQE** (below) Spark merges small ones automatically.

## 5. The optimizer: Catalyst, Tungsten, AQE

1. **Catalyst** turns your code into a *logical plan*, applies rules (predicate pushdown, column pruning, constant folding, join reordering), picks a *physical plan*. See it with `df.explain(True)`: parsed, analyzed, optimized, physical.
2. **Tungsten** executes it with off-heap binary memory and generated Java code ("whole-stage codegen"; the `*` in the plan marks it).
3. **Adaptive Query Execution (AQE, on by default since 3.2):** re-optimizes at runtime using real statistics from finished stages. It (a) coalesces small shuffle partitions, (b) switches a sort-merge join to a broadcast join when one side turns out small, (c) splits skewed partitions in skew joins.

```python
df.filter(F.col("status") == "done").select("location", "amount").explain(True)
```

**Predicate pushdown:** when reading Parquet/Iceberg, filters are pushed into the file scan so non-matching row groups/files are never read. Look for `PushedFilters` in the plan. That is why we filter 2023 and the test app *early* in the metrics layer.

## 6. Core DataFrame operations you must know cold

```python
df.select("order_id", (F.col("amount") * 1.1).alias("gross"))
df.filter((F.col("status") == "done") & (F.col("amount") > 10))     # & | ~ with parentheses!
df.withColumn("is_big", F.col("amount") >= 15)
df.withColumnRenamed("amount", "total")
df.drop("status")
df.dropDuplicates(["order_id"])
df.orderBy(F.col("amount").desc())
df.groupBy("location").agg(F.count("*").alias("orders"), F.round(F.sum("amount"), 2).alias("revenue"))
df.withColumn("band", F.when(F.col("amount") < 10, "small").when(F.col("amount") < 20, "mid").otherwise("large"))
df.na.fill({"status": "unknown"});  df.na.drop(subset=["amount"])
```

**Pitfalls interviewers like:**
- Use `&`, `|`, `~` with parentheses, not `and/or/not`.
- `F.col("x") == None` is never true; use `.isNull()` / `.isNotNull()`.
- `count("col")` ignores nulls; `count("*")` does not.
- `==` on nulls gives null, not false; filters drop null rows.
- Money must be `DecimalType` (`DECIMAL(18,2)`), never float: floats give 0.1 + 0.2 = 0.30000000000000004. This project uses decimals for every amount.
- Dates: parse with an explicit format (`F.to_timestamp("c", "yyyy-MM-dd'T'HH:mm:ss'Z'")`). Time zones: store UTC, convert with `F.from_utc_timestamp(ts, "America/New_York")` for the business day (see `config/business_rules.yaml`).

## 7. Joins

```python
orders = spark.createDataFrame([(1, 10), (2, 11), (3, 99)], "order_id int, cust_id int")
custs = spark.createDataFrame([(10, "Ana"), (11, "Bo"), (12, "Cy")], "cust_id int, name string")
orders.join(custs, "cust_id", "left").show()      # inner, left, right, full, left_semi, left_anti, cross
```

| Join type | Result |
|---|---|
| inner | rows with a match on both sides |
| left / right / full | keep all rows from that side (or both), nulls where no match |
| **left_semi** | rows from the left that HAVE a match; only left columns (an "exists" filter) |
| **left_anti** | rows from the left with NO match (the "not exists" filter; great for finding orphan keys) |
| cross | every pair; almost always a mistake |

**Join strategies (very common interview topic):**

| Strategy | How | When chosen |
|---|---|---|
| **Broadcast hash join** | the small table is copied to every executor; no shuffle of the big table | one side < `spark.sql.autoBroadcastJoinThreshold` (10 MB default), or you hint `F.broadcast(small)` |
| **Sort-merge join** | both sides shuffled by key and sorted, then merged | default for two large tables |
| **Shuffle hash join** | shuffle both, build a hash table of the smaller side per partition | when sort-merge is not needed and one side is much smaller |
| **Broadcast nested loop / cartesian** | compare all pairs | non-equi joins or cross joins: slow |

```python
from pyspark.sql.functions import broadcast
orders.join(broadcast(custs), "cust_id").explain()      # look for BroadcastHashJoin
```

In this project the dimensions (`dim_location`, `dim_item`, …) are small, so facts join them by broadcast.

**Duplicate-key trap:** joining on a key that is not unique multiplies rows (many-to-many explosion). Revenue then looks too high. That is why this project has data-quality checks that compare revenue across orders, lines and aggregates.

## 8. Skew and how to fix it

**Skew:** one key has far more rows than the others (for example a guest `user_id = NULL`, or one restaurant). After a shuffle one task gets most of the data; the stage waits for that one straggler. In the Spark UI: one task takes 10 minutes while the others take seconds; one task's "shuffle read size" is huge.

Fixes, in the order to try:
1. **Turn on AQE skew join** (`spark.sql.adaptive.skewJoin.enabled`, default true): splits big partitions automatically.
2. **Filter or handle the hot key separately** (for example process NULL keys on their own).
3. **Broadcast** the smaller side so there is no shuffle.
4. **Salting:** add a random suffix to the hot key on the big side and replicate the small side across all suffixes, join, then aggregate away the salt.

```python
salt_n = 8
big = big.withColumn("salt", (F.rand() * salt_n).cast("int"))
small = small.crossJoin(spark.range(salt_n).withColumnRenamed("id", "salt"))
joined = big.join(small, ["key", "salt"])
```

## 9. Partitioning: repartition, coalesce, partitionBy

| Call | What it does | Cost |
|---|---|---|
| `df.repartition(n)` or `repartition(n, "col")` | full shuffle into n balanced partitions (or hash by column) | shuffle |
| `df.coalesce(n)` | merge down to fewer partitions without a full shuffle (can only decrease) | cheap |
| `df.write.partitionBy("year", "month")` | folder-per-value layout on disk | affects reads |
| `bucketBy(n, "col")` | pre-hash into n files per partition so joins on that key skip the shuffle (Hive tables only) | rare |

**Rules:**
- Use `coalesce` to reduce the number of output files before a write; use `repartition` to increase parallelism or balance data.
- Partition **on disk** by a column with **low cardinality** that queries filter on (date, country). Partitioning by `customer_id` creates millions of tiny folders.
- **Small files problem:** thousands of tiny files make reads slow (listing, opening each). Cause: too many partitions at write time or many small incremental writes. Fixes: coalesce before writing, a compaction job (Iceberg `rewrite_data_files`, chapter A8).
- Target file size on disk: roughly 128 MB to 1 GB.

## 10. Caching and persistence

```python
d = df.filter(F.col("status") == "done")
d.cache()            # = persist(StorageLevel.MEMORY_AND_DISK); lazy: filled by the first action
d.count(); d.count() # second count reads from memory
d.unpersist()
```

Cache a DataFrame **used more than once** after expensive work (a big join, an aggregation). Do not cache by habit: it uses executor memory that the shuffle also needs, and a DataFrame that is read once gains nothing. Storage levels: `MEMORY_ONLY`, `MEMORY_AND_DISK`, `DISK_ONLY`, with `_SER` (serialized, smaller, slower) and `_2` (two copies).

**`checkpoint()`** writes to storage and cuts the plan's history (lineage): useful when a plan gets so long it is slow to plan, or in streaming.

## 11. Window functions

A window computes a value per row from a group of related rows, without collapsing them (unlike `groupBy`).

```python
w = Window.partitionBy("location").orderBy(F.col("amount").desc())
df.withColumn("rank_in_location", F.row_number().over(w)).show()

running = Window.partitionBy("location").orderBy("order_id").rowsBetween(Window.unboundedPreceding, Window.currentRow)
df.withColumn("running_revenue", F.sum("amount").over(running)).show()
df.withColumn("prev_amount", F.lag("amount", 1).over(Window.partitionBy("location").orderBy("order_id"))).show()
```

| Function | Use |
|---|---|
| `row_number()` | unique 1, 2, 3 per partition (pick the latest row per key) |
| `rank()` / `dense_rank()` | ties share a rank; rank leaves gaps, dense_rank does not |
| `lag` / `lead` | previous/next row's value (days since last order) |
| `sum/avg/count().over(frame)` | running totals, moving averages |
| `ntile(n)` | split into n equal buckets (quintiles, "top 20 %") |

**Dedup pattern (very common):** keep the newest row per key:

```python
w = Window.partitionBy("order_id").orderBy(F.col("updated_at").desc())
latest = df.withColumn("rn", F.row_number().over(w)).filter("rn = 1").drop("rn")
```

A window with `partitionBy` triggers a shuffle; without `partitionBy` all rows go to ONE task (a warning in the logs, and slow).

In this project: `metrics/customer_snapshot.py` builds a row per customer per day and uses windows for running CLV, recency and 90-day frequency.

## 12. UDFs, built-ins and pandas UDFs

- **Built-in functions** (`pyspark.sql.functions`) run inside the JVM and are optimized. **Always prefer them.**
- A **Python UDF** (`F.udf`) ships each row from the JVM to a Python process and back: slow, and invisible to the optimizer.
- A **pandas UDF** (`@F.pandas_udf`) moves data in Arrow batches: much faster than a plain UDF, still slower than built-ins.

```python
@F.udf("string")
def shout(s): return s.upper() + "!"          # works, but slow; F.upper(F.col("s")) is better
```

Interview line: "I express logic with built-in functions and Spark SQL; a UDF is the last resort."

## 13. File formats

| Format | Type | Notes |
|---|---|---|
| **CSV / JSON** | row, text, no types (CSV) | human-readable, slow, ambiguous; seed data only here |
| **Parquet** | columnar, compressed, typed, splittable | the default for analytics; column pruning + predicate pushdown via min/max stats per row group |
| **ORC** | columnar | like Parquet, common in Hive worlds |
| **Avro** | row-based, schema in file | good for streaming/Kafka and schema evolution |
| **Delta / Iceberg / Hudi** | table formats over Parquet files | add transactions, MERGE, time travel (chapter A8) |

**Why columnar?** An analytics query touches 3 of 40 columns. Columnar storage reads only those 3 and compresses similar values well.

Spark reads CSV with `spark.read.option("header", True).option("multiLine", True).option("escape", '"').schema(schema).csv(path)`. This project needs `multiLine` and `escape` because the CSV fields contain quoted newlines and quotes.

## 14. Reading and writing, save modes, idempotent writes

```python
df.write.mode("overwrite").parquet("/tmp/out")     # append | overwrite | ignore | errorifexists
```

- `overwrite` of a whole folder is dangerous (if the job fails midway, data is gone). Plain Parquet overwrites are **not atomic**.
- A table format (Iceberg) gives atomic commits: readers see the old or the new version, never half.
- **Idempotent** = running twice gives the same result. Recipes: MERGE on a business key (this project's silver and gold), overwrite one partition, or write to a staging path then swap. **Never plain `append` of a day that may be re-run.**

## 15. Memory, spill and common failures

| Symptom | Likely cause | Fix |
|---|---|---|
| `OutOfMemoryError` on the **driver** | `collect()`/`toPandas()` of a big result, or a huge broadcast | stop collecting; write out; raise driver memory |
| `OutOfMemoryError`/`Container killed by YARN for exceeding memory` on an **executor** | skewed partition, too-large partitions, big cache | more partitions, fix skew, more executor memory/overhead |
| One task much slower than the rest | skew | section 8 |
| Job slow, thousands of tiny tasks | too many small files or partitions | coalesce, compaction, AQE |
| Job slow, few huge tasks | too few partitions | repartition |
| Shuffle spill to disk (UI "Spill (disk)") | partitions do not fit in execution memory | more partitions or memory |
| `AnalysisException: cannot resolve column` | typo or ambiguous join columns | alias / use `df["col"]` |
| Long GC pauses | many objects, big caches | fewer cached objects, serialized storage |

**Memory model (unified memory):** each executor's heap is split into *reserved*, *user memory*, and a *unified region* shared by **execution** (shuffles, joins, sorts) and **storage** (cache). They can borrow from each other; execution can evict cache. `spark.executor.memory`, `spark.executor.memoryOverhead` (off-heap, important for PySpark), `spark.memory.fraction`.

## 16. Reading the Spark UI (what to look at)

Locally this project exposes it at http://localhost:18080 (Spark History server) after a job has finished. A running job shows its UI on port 4040.

| Tab | Look for |
|---|---|
| **Jobs** | which action created which job; failed jobs |
| **Stages** | duration per stage; the task-time distribution (min / median / max: a large max = skew); shuffle read/write sizes; spill |
| **SQL / DataFrame** | the physical plan as a graph, with row counts per node; where the shuffles are |
| **Storage** | what is cached and how much |
| **Executors** | memory and GC time per executor; dead executors |

Method: find the slowest stage, open it, compare the max task to the median, then look at its shuffle/IO.

## 17. Spark on AWS Glue (this project)

- **Glue job** = a managed Spark job: you pay per **DPU-hour** (here G.1X workers: 4 vCPU, 16 GB each, billed per second with a 1-minute minimum). The cluster starts for each run (cold start about 30 to 60 s).
- `--datalake-formats iceberg` enables the Iceberg libraries; the Glue Data Catalog is the Iceberg catalog (`config/environments.yaml`, `prod.catalog.type: glue`).
- Parameters arrive as `--KEY value` arguments (`common/job_args.py`).
- The job reads the source over **JDBC** (RDS SQL Server): `spark.read.format("jdbc")`. JDBC reads are single-threaded unless you give `partitionColumn`, `lowerBound`, `upperBound`, `numPartitions`. A long JDBC statement against a tiny database is a real bottleneck: our year-size replay hung inside one SQL Server transaction (decisions.md, 2026-11-02).
- Local and AWS run the same code; only `PIPELINE_ENV` and `config/environments.yaml` differ.

## 18. Structured Streaming (the interview basics)

This project is batch, but interviews ask about streaming.

- **Micro-batch model:** a stream is an unbounded table; Spark processes new data in small batches (a trigger interval) using the same DataFrame API. Alternative: continuous mode (experimental).
- **Sources/sinks:** Kafka, files, sockets (testing) / Kafka, files, Delta/Iceberg, foreachBatch.
- **Checkpoint:** a folder where Spark stores progress (offsets) and state, so a restarted query continues exactly where it stopped. Required for fault tolerance.
- **Output modes:** `append` (only new final rows), `update` (changed rows), `complete` (the whole result table; for aggregations).
- **Event time vs processing time:** event time is when something happened (a field in the data); processing time is when Spark sees it. Late data is common.
- **Watermark:** `withWatermark("event_time", "10 minutes")` tells Spark how late data can be; state older than the watermark is dropped, and windows are finalized. Needed to bound state in aggregations/joins.
- **Windows:** `F.window("event_time", "5 minutes")` (tumbling) or with a slide (sliding).
- **Delivery guarantees:** with a replayable source (Kafka) + checkpoint + an idempotent sink, you get **end-to-end exactly-once**.
- **Batch vs streaming for this project:** daily batch is enough (CLV changes daily; the SME asked for daily). Streaming would add cost and complexity.

## 19. Performance tuning checklist (say this in an interview)

1. Read less: filter early, select only needed columns, use columnar formats with predicate pushdown, partition data by a column that queries filter on.
2. Avoid shuffles: broadcast small tables; avoid repeated `distinct`/`orderBy`; pre-aggregate before joining.
3. Right-size partitions: about 100 to 200 MB each; let AQE coalesce.
4. Handle skew: AQE skew join, isolate hot keys, salting.
5. Prefer built-ins over UDFs; pandas UDFs if needed.
6. Cache only what is reused.
7. Fix the small-files problem at write time and with compaction.
8. Measure with the Spark UI before and after; change one thing at a time.
9. Tune cluster size last: more machines do not fix skew.

## 20. Where each concept is in this project

| Concept | File |
|---|---|
| Explicit schemas, parsing, no guessing | `transformations/cleaning.py`, `silver_order_items.py` |
| Joins with small dimensions | `transformations/gold_facts.py`, `gold_dimensions.py` |
| Windows (running CLV, recency, frequency) | `metrics/customer_snapshot.py` |
| Aggregations | `metrics/sales.py`, `metrics/location.py` |
| JDBC reads, watermark + 3-day lookback | `common/sqlserver.py`, `jobs/extract_to_bronze.py` |
| MERGE into Iceberg (idempotent) | `jobs/bronze_to_silver.py`, `silver_to_gold.py` |
| Session setup, catalogs | `common/spark.py`, `common/tables.py` |
| Spark in tests | `tests/conftest.py` |

## 21. Practice (type these; each has one right answer)

Run in the container's Python prompt after the setup above.

**P1. Counts and sums.** Build the 10-order dataset from chapter A1 (`order_id, location, amount, status`) as a DataFrame. Compute revenue of `done` orders per location. Expected: boston 50.5, cambridge 26.35, somerville 40.4.

```python
rows = [(1,"boston",12.50,"done"),(2,"boston",8.00,"done"),(3,"cambridge",15.25,"done"),(4,"cambridge",9.75,"refunded"),
        (5,"somerville",22.00,"done"),(6,"boston",5.50,"cancelled"),(7,"somerville",18.40,"done"),(8,"cambridge",11.10,"done"),
        (9,"boston",30.00,"done"),(10,"somerville",7.25,"refunded")]
orders = spark.createDataFrame(rows, "order_id int, location string, amount double, status string")
orders.filter(F.col("status") == "done").groupBy("location").agg(F.round(F.sum("amount"), 2).alias("revenue")).orderBy("location").show()
```

**P2. Window.** Add each order's rank by amount within its location. Expected: for boston, order 9 is rank 1, order 1 rank 2, order 2 rank 3, order 6 rank 4.

**P3. Dedup.** Create duplicates of `order_id` with different `amount` and keep the one with the largest amount per order (row_number). Prove with `count()` before and after.

**P4. Anti-join.** Create a `custs` table with some ids missing from `orders` and use `left_anti` to list orders with no customer. Expected: exactly the ids you left out.

**P5. Plans.** Run `explain()` on a `groupBy` and on a join with and without `broadcast()`. Write down where `Exchange` appears and where it does not.

**P6. Skew experiment.** Build 1,000,000 rows where 90 % have `key = 0`. Group by key and open http://localhost:4040 while running (use `.count()` on a long loop or `time.sleep`). Which task is the slowest?

**P7. Small files.** Write the same 1,000,000 rows with `repartition(200)` and with `coalesce(1)` to two folders and compare the file counts with `ls`. Explain the trade-off.

**P8. Read this project.** Open `src/globalpartners/metrics/customer_snapshot.py`. Explain in 5 sentences how one customer-day row is produced and which operations trigger shuffles.

## 22. Interview questions with model answers

1. **What is Spark and how does it differ from MapReduce?** A distributed engine that keeps intermediate data in memory and plans a DAG of stages; MapReduce writes to disk between every map and reduce.
2. **Explain driver, executor, cluster manager.** (section 1)
3. **What is lazy evaluation and why does it matter?** Transformations only build a plan; actions run it. Lets Catalyst optimize across steps. A reused DataFrame is recomputed unless cached.
4. **Narrow vs wide transformation?** (section 4) Wide ones need a shuffle.
5. **What is a shuffle and why is it expensive?** Data is redistributed by key across the network, written to disk and read back; involves serialization, disk and network IO.
6. **How many partitions should I have?** Enough for all cores to be busy and each about 100 to 200 MB; 2 to 4 times the total cores is a start; let AQE coalesce after shuffles.
7. **`repartition` vs `coalesce`?** repartition = full shuffle, can increase or balance; coalesce = narrow merge, only decreases.
8. **How do you handle data skew?** (section 8)
9. **Explain broadcast join; when would it fail?** Small table copied to all executors; fails (OOM) if the "small" table is actually big, or exceeds driver memory when collected for broadcast.
10. **What is AQE?** (section 5)
11. **cache vs persist vs checkpoint?** cache = persist with the default level; persist lets you choose; checkpoint writes to reliable storage and truncates lineage.
12. **Why prefer DataFrames over RDDs?** Optimizer + Tungsten + schema.
13. **Why are UDFs slow? Alternatives?** JVM-to-Python serialization per row; use built-ins or pandas UDFs.
14. **What is a DAG?** The graph of stages/tasks for a job. Failed tasks are recomputed from lineage.
15. **How does Spark achieve fault tolerance?** Lineage: lost partitions are recomputed from their parents; shuffle files and checkpoints help.
16. **Parquet vs CSV?** (section 13)
17. **What is predicate pushdown / column pruning / partition pruning?** Skip data that cannot match: filters in the scan, only needed columns, only needed folders.
18. **How do you deduplicate?** `dropDuplicates` for exact duplicates; window `row_number` to keep the latest per key; MERGE for table upserts.
19. **How do you do an incremental load?** Keep a watermark (max timestamp loaded), read `> watermark - lookback`, MERGE on the key, advance the watermark only after success. (This project, `extract_to_bronze`.)
20. **How would you make a pipeline idempotent?** MERGE or partition overwrite, deterministic transformations, no plain appends.
21. **Rank vs dense_rank vs row_number?** (section 11)
22. **How do you read a query plan?** Bottom to top; look for Scan (with pushed filters), Exchange (shuffle), joins (which strategy), HashAggregate/Sort.
23. **What causes OOM and how do you fix it?** (section 15)
24. **What is the small-files problem?** (section 9)
25. **Structured streaming: what is a watermark?** (section 18)
26. **How do you test PySpark code?** Keep transformations as pure functions on DataFrames; use a local `SparkSession` fixture and tiny DataFrames with known answers; this project's `tests/` do exactly that.
27. **How do you debug a slow job?** Spark UI: slowest stage, task-time distribution, shuffle sizes, spill; then fix the cause (skew, partitions, join strategy).
28. **Spark vs pandas vs SQL warehouse (Snowflake, Redshift)?** Choose by data size, team skills and cost; Spark shines for large-scale transformation on a lake and complex logic in Python; SQL warehouses for SQL-first teams.
29. **What happens when you call `count()` on a CSV with a wrong schema?** The parse mode decides: `PERMISSIVE` (default) puts nulls and keeps `_corrupt_record`, `DROPMALFORMED` drops, `FAILFAST` raises. This project routes unusable rows to a quarantine table instead.
30. **Why DECIMAL for money?** Binary floats cannot represent most decimal fractions exactly; sums drift. Decimals are exact.

## Done when

You can (1) draw driver/executors/partitions/shuffle from memory, (2) read `explain()` output and name each node, (3) pick a join strategy and justify it, (4) fix a skewed aggregation, (5) answer questions 1 to 30 without notes, (6) all practice P1 to P8 done.
