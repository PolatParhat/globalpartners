# Stage B5: the SQL Server source and the daily replay

**Goal:** a real source database (SQL Server in Docker) that receives one business day of orders at a time, like the restaurants' system. Prerequisites: chapters A5, A6.

## Why a replay

The CSVs are a static snapshot, but the pipeline must handle daily arrival. So we load all rows into `seed.*` tables and a stored procedure copies one business day (New York time) into the live `dbo.*` tables.

## Steps

1. **`docker-compose.yml`:** add the `sqlserver` service: image `mcr.microsoft.com/mssql/server:2022-latest`, `platform: linux/amd64` (it runs under Rosetta on an M-series Mac), env `ACCEPT_EULA=Y`, `MSSQL_SA_PASSWORD` from `.env`, port 1433, a named volume `mssql-data:/var/opt/mssql`, a health check using `sqlcmd`.
2. **`.env`** (never committed; add to `.gitignore`): `MSSQL_SA_PASSWORD`, plus the read-only login's name and password.
3. **`sql/01_create_database.sql`:** create database `globalpartners`, schemas `dbo` and `seed`, and a login/user `etl_reader` with **read-only** rights on `dbo`. Least privilege starts here.
4. **`sql/02_create_tables.sql`:** tables `order_items`, `order_item_options`, `date_dim` in both `seed` and `dbo`; money as `DECIMAL(18,2)`; indexes on `order_id`. **Warning (a real lesson):** this script DROPs and recreates tables; run it only on a new database.
5. **Load the CSVs into `seed.*`** (a job `load_seed` using Spark/JDBC, or `BULK INSERT` / `bcp`).
6. **`sql/03_replay_procedure.sql`:** `seed.replay_days @from_date, @to_date = NULL`. Logic: find the orders whose New York business date is in the range and not yet in `dbo` (idempotent), then in **one transaction** insert their lines and options into `dbo`. `NOT EXISTS` makes a second run add nothing.

```bash
docker compose up -d sqlserver
docker compose exec sqlserver /opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -i /path/in/container/01_create_database.sql
```

## Check

```sql
EXEC seed.replay_days '2023-01-01';   -- then 2023-01-02, then 2023-01-03
```

Expected, per day (orders / lines / options / revenue): **63 / 120 / 105 / $1,078.19**, **96 / 159 / 173 / $1,424.16**, **130 / 184 / 151 / $1,681.19**. After all three: 289 orders, 463 lines, 429 options. Running the same day again adds 0.

## Experiments

- Run `EXEC seed.replay_days '2023-01-01', '2023-12-31'` on a tiny machine and watch it: one huge transaction (this hung on the AWS db.t3.micro). Replay in chunks instead.
- Kill the client mid-run; the transaction rolls back (SQL Server keeps working on the rollback after the client is gone).

## Compare with the real project

`sql/01`–`03`, `docker-compose.yml`, `src/globalpartners/jobs/setup_source.py`, `load_seed.py`, `replay_day.py`.

## Done when

The three replay days match the numbers above and a second run adds nothing.
