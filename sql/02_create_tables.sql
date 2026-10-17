-- Step 4.2: source tables. Typed columns, like a real order system.
-- No NOT NULL or unique-key rules on purpose: the real data has quirks (e.g. a line with no
-- lineitem_id) and they must reach the pipeline, where quarantine handles them.
-- dbo.*  = the live tables the pipeline reads (filled by the replay)
-- seed.* = every row from the CSV files (filled once by load_seed.py)

USE globalpartners;
GO

DROP TABLE IF EXISTS dbo.order_items, dbo.order_item_options, dbo.date_dim,
                     seed.order_items, seed.order_item_options;
GO

CREATE TABLE dbo.order_items (
    app_name             NVARCHAR(100),
    restaurant_id        VARCHAR(50),
    creation_time_utc    DATETIME2(3),      -- UTC, millisecond precision
    order_id             VARCHAR(50),
    user_id              VARCHAR(50),       -- NULL = guest order
    printed_card_number  VARCHAR(32),
    is_loyalty           BIT,
    currency             CHAR(3),
    lineitem_id          VARCHAR(50),
    item_category        NVARCHAR(200),
    item_name            NVARCHAR(200),
    item_price           DECIMAL(10,2),     -- line total
    item_quantity        INT
);

CREATE TABLE dbo.order_item_options (
    order_id             VARCHAR(50),
    lineitem_id          VARCHAR(50),
    option_group_name    NVARCHAR(200),
    option_name          NVARCHAR(200),
    option_price         DECIMAL(10,2),
    option_quantity      INT
);

CREATE TABLE dbo.date_dim (
    date_key             DATE,
    year                 INT,
    month                INT,
    week                 INT,
    day_of_week          VARCHAR(10),
    is_weekend           BIT,
    is_holiday           BIT,
    holiday_name         NVARCHAR(100)
);
GO

-- seed tables: same columns as the live tables
SELECT TOP 0 * INTO seed.order_items        FROM dbo.order_items;
SELECT TOP 0 * INTO seed.order_item_options FROM dbo.order_item_options;
GO

-- indexes for the queries that will run: the extract's time window and lo
CREATE INDEX ix_order_items_creation_time ON dbo.order_items (creation_time_utc);
CREATE INDEX ix_order_items_order_id      ON dbo.order_items (order_id);
CREATE INDEX ix_options_order_id          ON dbo.order_item_options (order_id);
CREATE INDEX ix_seed_items_order_id       ON seed.order_items (order_id);
CREATE INDEX ix_seed_options_order_id     ON seed.order_item_options (order_id);
GO

PRINT 'tables created: dbo.order_items, dbo.order_item_options, dbo.date_dd.order_item_options';