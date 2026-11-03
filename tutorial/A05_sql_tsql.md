# Chapter A5: SQL and T-SQL (SQL Server)

**Time:** 2 sessions. **Goal:** write the SQL every data engineering interview asks for, and read `sql/01`–`03` and `dashboard/queries.py`.
**Practice database:** the local SQL Server (`docker compose up -d sqlserver`) or the Spark SQL prompt on the lake (see `STATUS.md`, "Lake SQL prompt"). Standard SQL below works in SQL Server, Spark SQL and Athena; differences are marked.

## 1. How a query runs (mental order)

You write `SELECT … FROM … WHERE … GROUP BY … HAVING … ORDER BY …`. The engine runs: **FROM/JOIN → WHERE → GROUP BY → HAVING → SELECT → ORDER BY → LIMIT/TOP**. Consequences: you cannot use a SELECT alias in WHERE; WHERE filters rows, HAVING filters groups.

## 2. Core statements

```sql
SELECT location, SUM(amount) AS revenue
FROM orders
WHERE status = 'done'
GROUP BY location
HAVING SUM(amount) > 30
ORDER BY revenue DESC;
```

- `COUNT(*)` counts rows; `COUNT(col)` ignores NULLs; `COUNT(DISTINCT col)`.
- NULL: unknown. `x = NULL` is never true; use `IS NULL`. `NULL + 1` is NULL. `COALESCE(a, b, 0)` returns the first non-null.
- `CASE WHEN amount < 10 THEN 'small' ELSE 'large' END`.
- `LIKE 'bos%'`, `IN ('a','b')`, `BETWEEN 1 AND 5`, `DISTINCT`.
- Limit rows: SQL Server `SELECT TOP 10 …` or `ORDER BY … OFFSET 0 ROWS FETCH NEXT 10 ROWS ONLY`; Spark/Athena `LIMIT 10`.

## 3. Joins

| Join | Rows returned |
|---|---|
| `INNER JOIN` | matches on both sides |
| `LEFT JOIN` | all left rows, NULLs where no match |
| `RIGHT / FULL JOIN` | all right / all rows from both |
| `CROSS JOIN` | every pair |
| semi (`WHERE EXISTS`) / anti (`WHERE NOT EXISTS`, or `LEFT JOIN … WHERE b.id IS NULL`) | left rows that do / do not have a match |

**Row explosion:** joining on a non-unique key multiplies rows and inflates sums. Always know the grain of both sides. (This project's checks compare revenue across tables for exactly this reason.)

## 4. Aggregation, subqueries, CTEs

```sql
WITH done AS (SELECT * FROM orders WHERE status = 'done'),
     per_loc AS (SELECT location, SUM(amount) AS revenue FROM done GROUP BY location)
SELECT * FROM per_loc WHERE revenue > 30;
```

A **CTE** (`WITH`) names a subquery for readability and reuse. Subqueries can be in `FROM`, `WHERE … IN (SELECT …)`, or correlated. Prefer CTEs for clarity.

## 5. Window functions (the most-asked topic)

```sql
SELECT order_id, location, amount,
       ROW_NUMBER() OVER (PARTITION BY location ORDER BY amount DESC) AS rn,
       SUM(amount)  OVER (PARTITION BY location ORDER BY order_id
                          ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running,
       LAG(amount)  OVER (PARTITION BY location ORDER BY order_id) AS prev_amount,
       NTILE(5)     OVER (ORDER BY amount) AS quintile
FROM orders;
```

- `ROW_NUMBER` unique; `RANK` ties with gaps; `DENSE_RANK` ties without gaps.
- Windows keep every row (unlike GROUP BY).
- **Latest row per key:** `ROW_NUMBER() … ORDER BY updated_at DESC` then keep `rn = 1`.
- **Gaps and islands, running totals, moving averages, "days since previous order" (`LAG`)**: all windows.

## 6. Dates and time zones

SQL Server: `DATEADD(day, -90, GETDATE())`, `DATEDIFF(day, a, b)`, `CAST(x AS date)`, `FORMAT`/`CONVERT`, `AT TIME ZONE`. Spark/Athena: `date_add`, `datediff`, `date_trunc`, `from_utc_timestamp`. This project stores **UTC** and converts to `America/New_York` for the business day. Be explicit about the format (`dd-MM-yyyy` in `date_dim`).

## 7. DDL, constraints, indexes, keys

- `CREATE TABLE`, `PRIMARY KEY`, `FOREIGN KEY`, `NOT NULL`, `UNIQUE`, `CHECK`, `DEFAULT`. Types: use `DECIMAL(18,2)` for money, never float.
- **Index:** a sorted structure that makes lookups on a column fast, at the cost of slower writes and space. Clustered (defines the table's physical order; one per table) vs non-clustered. `sql/02_create_tables.sql` indexes `order_id`. An index helps `WHERE`/`JOIN` on those columns, not `LIKE '%x'`.
- **Normalization:** 1NF (atomic values), 2NF/3NF (no partial/transitive dependencies). OLTP normalizes; analytics denormalizes (star schema, chapter A3).

## 8. Transactions, ACID, locks

- **Transaction:** a group of statements that succeed or fail together (`BEGIN TRAN … COMMIT / ROLLBACK`).
- **ACID:** Atomicity (all or nothing), Consistency (rules hold), Isolation (concurrent transactions do not see each other's half-done work), Durability (committed = survives a crash).
- **Isolation levels:** read uncommitted, read committed (SQL Server default), repeatable read, serializable, snapshot. Higher = fewer anomalies (dirty read, non-repeatable read, phantom), more blocking.
- **Locks and blocking:** long transactions hold locks; others wait. **Deadlock:** two transactions wait on each other; the engine kills one.
- **Real lesson from this project:** replaying a whole year in one statement ran as one huge transaction on a tiny database; killed clients leave transactions rolling back (a rollback can take as long as the work). We loaded in chunks instead.

## 9. MERGE (upsert)

```sql
MERGE INTO target t
USING source s ON t.order_id = s.order_id
WHEN MATCHED THEN UPDATE SET t.amount = s.amount
WHEN NOT MATCHED THEN INSERT (order_id, amount) VALUES (s.order_id, s.amount);
```

"Update if it exists, insert if not." Makes reruns safe (idempotent). Same idea in Iceberg/Spark SQL (`MERGE INTO … WHEN MATCHED … WHEN NOT MATCHED …`). Watch out: the source must have at most one row per key or MERGE errors/duplicates.

## 10. Stored procedures and T-SQL scripting

`sql/03_replay_procedure.sql` defines `seed.replay_days(@from, @to)`: a stored procedure (a saved, parameterized script) that copies a day's orders from the seed tables into the live tables, called as `EXEC seed.replay_days '2023-01-01', '2023-01-03'`. T-SQL has variables (`DECLARE @x int = 1`), `IF/ELSE`, `WHILE`, `TRY…CATCH`, temp tables (`#t`).
Logins vs users vs permissions: `sql/01_create_database.sql` creates a read-only `etl_reader` login: least privilege.
Tool: `sqlcmd -C -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -d globalpartners -Q "SELECT COUNT(*) FROM dbo.order_items"` (`-C` trust the certificate).

## 11. Query performance

Read the **execution plan** (SSMS/Azure Data Studio "Include Actual Plan"; `EXPLAIN` in Spark/Athena). Look for table scans on big tables, missing indexes, sorts, row estimates far from actual. Tips: filter early, select only needed columns, avoid functions on indexed columns in WHERE (`WHERE YEAR(d) = 2023` blocks an index; use a range), avoid `SELECT *`, keep statistics up to date.

## 12. Exercises on this project's data

Known answers for 2023 (in scope): **52,015 orders, revenue $746,223.86, 10,512 customers, 20 locations**.

1. Count rows of `dbo.order_items` and of distinct `order_id`. (Differs: one order has several lines.)
2. Revenue per location, descending; check the total.
3. Orders per month in New York time; the busiest month.
4. Customers with exactly one order vs more than one.
5. For each customer, days between consecutive orders (`LAG`).
6. The latest order per customer (`ROW_NUMBER`).
7. Rewrite the churn rule: active ≤ 45 days since last order, at risk 46 to 90, lapsed over 90, as a `CASE` on `DATEDIFF`.
8. Use `LEFT JOIN … IS NULL` to find orders with no options, and `NOT EXISTS` for the same result.
9. Explain why `COUNT(*)` and `COUNT(location)` could differ.
10. Read `dashboard/queries.py` and rewrite two queries by hand.

(Solutions to check your work: the references in `CLAUDE.md` "Key facts". Query results on the gold tables should hit those exact numbers.)

## Interview questions

1. WHERE vs HAVING? 2. INNER vs LEFT join? 3. Find duplicates and delete all but one. 4. Second highest salary (window or subquery). 5. Running total. 6. RANK vs DENSE_RANK vs ROW_NUMBER. 7. What is an index; when does it not help? 8. ACID; isolation levels; what is a deadlock? 9. CTE vs temp table vs subquery. 10. How do you find rows in A not in B? 11. What is a NULL and how do aggregates treat it? 12. UNION vs UNION ALL (ALL keeps duplicates, faster). 13. Explain MERGE and idempotency. 14. Clustered vs non-clustered index. 15. How do you tune a slow query?

## Done when

You complete exercises 1 to 10, and the aggregate numbers match the reference values.
