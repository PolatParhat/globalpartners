-- Step 4.2: the source database, its seed schema and a read-only login for the pipeline.
-- Run as sa. Safe to run again: every statement checks before it creates.

IF DB_ID('globalpartners') IS NULL
    CREATE DATABASE globalpartners;
GO

USE globalpartners;
GO

-- seed = all rows from the CSV files; the replay copies them into dbo one day at a time
IF SCHEMA_ID('seed') IS NULL
    EXEC('CREATE SCHEMA seed');
GO

-- The pipeline's extract job logs in as etl_reader: it can only read the live (dbo) tables.
IF SUSER_ID('etl_reader') IS NULL
    CREATE LOGIN etl_reader WITH PASSWORD = '$(ETL_PASSWORD)', CHECK_POLICY = ON;
GO

IF USER_ID('etl_reader') IS NULL
    CREATE USER etl_reader FOR LOGIN etl_reader;
GO

GRANT SELECT ON SCHEMA::dbo TO etl_reader;
GO

PRINT 'database globalpartners, schema seed and login etl_reader are ready';