-- Step 4.2: replay. Copies the orders of a range of business days (New York time) from
-- seed.* into the live dbo.* tables, together with their options, as if those days
-- had just been traded. Running the same days again adds nothing (no duplicates).
--
--   EXEC seed.replay_days '2023-01-01';                 -- one day
--   EXEC seed.replay_days '2023-01-01', '2023-01-31';   -- a range of days

USE globalpartners;
GO

CREATE OR ALTER PROCEDURE seed.replay_days
    @from_date DATE,
    @to_date   DATE = NULL
AS
BEGIN
    SET NOCOUNT ON; -- stops SQL Server from sending "(5 rows affected)" messages after each statement.
    SET @to_date = COALESCE(@to_date, @from_date);

    -- orders whose New York business date falls in the range and are not live yet
    SELECT DISTINCT s.order_id
    INTO #orders -- temp orders table
    FROM seed.order_items AS s
    WHERE CAST(s.creation_time_utc AT TIME ZONE 'UTC' AT TIME ZONE 'Eastern Standard Time' AS DATE)
          BETWEEN @from_date AND @to_date
      AND NOT EXISTS (SELECT 1 FROM dbo.order_items AS d WHERE d.order_id = s.order_id);

    BEGIN TRANSACTION;   -- the lines and options of a day arrive together, or not at all

    INSERT INTO dbo.order_items
    SELECT s.* FROM seed.order_items AS s JOIN #orders AS o ON o.order_id = s.order_id;
    DECLARE @lines INT = @@ROWCOUNT;

    INSERT INTO dbo.order_item_options
    SELECT s.* FROM seed.order_item_options AS s JOIN #orders AS o ON o.order_id = s.order_id;
    DECLARE @options INT = @@ROWCOUNT;

    COMMIT;

    SELECT @from_date AS from_date, @to_date AS to_date,
           (SELECT COUNT(*) FROM #orders) AS orders_added, @lines AS lines_added, @options AS options_added;
END;
GO

PRINT 'procedure seed.replay_days is ready';