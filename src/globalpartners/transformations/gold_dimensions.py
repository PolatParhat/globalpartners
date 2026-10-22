"""silver → gold dimensions (spec: Step3_Data_Model.md, section 9). Rebuilt in full every run."""
from pyspark.sql import Column, DataFrame, SparkSession, Window
from pyspark.sql import functions as F

GUEST = "GUEST"

def item_key() -> Column:
    """An item is its normalised name + category (49 names appear in more than one category)."""
    return F.sha2(F.concat_ws("||", F.col("item_name_key"), F.coalesce(F.col("item_category"), F.lit(""))), 256)
  
  
def dim_customer(lines: DataFrame) -> DataFrame:
    """One row per user_id, plus one GUEST row for orders without a customer."""
    customers = (lines.where(F.col("user_id").isNotNull())
                 .groupBy(F.col("user_id").alias("customer_id"))
                 .agg(F.min("business_date").alias("first_order_date"),
                      F.max("business_date").alias("last_order_date"),
                      F.min(F.when(F.col("is_loyalty"), F.col("business_date"))).alias("first_loyalty_order_date"),
                      F.max(F.col("is_non_customer_account").cast("int")).cast("boolean").alias("is_non_customer_account"))
                 .withColumn("is_guest", F.lit(False)))
    guest = lines.sparkSession.createDataFrame(
        [(GUEST, None, None, None, False, True)],
        "customer_id string, first_order_date date, last_order_date date, "
        "first_loyalty_order_date date, is_non_customer_account boolean, is_guest boolean")
    return customers.unionByName(guest)
  
def dim_location(lines: DataFrame) -> DataFrame:
    """One row per restaurant_id. location_name stays empty: the source has ids only."""
    return (lines.groupBy("restaurant_id")
            .agg(F.min("business_date").alias("first_order_date"),
                 F.max("business_date").alias("last_order_date"),
                 F.min(F.col("is_test_data").cast("int")).cast("boolean").alias("is_test_location"))
            .withColumn("location_name", F.lit(None).cast("string"))
            .select("restaurant_id", "location_name", "first_order_date", "last_order_date", "is_test_location"))
    
def dim_item(lines: DataFrame) -> DataFrame:
    """One row per item (name + category); display name = the most common spelling, ties alphabetical."""
    keyed = lines.withColumn("item_key", item_key())
    spellings = keyed.groupBy("item_key", "item_name").count()
    most_common = Window.partitionBy("item_key").orderBy(F.col("count").desc(), F.col("item_name"))
    names = (spellings.withColumn("_rn", F.row_number().over(most_common))
             .where("_rn = 1").select("item_key", "item_name"))
    stats = (keyed.groupBy("item_key", "item_category")
             .agg(F.min("business_date").alias("first_sold_date"),
                  F.max("business_date").alias("last_sold_date")))
    return names.join(stats, "item_key").select("item_key", "item_name", "item_category",
                                               "first_sold_date", "last_sold_date")
    
def dim_app(lines: DataFrame, rules: dict) -> DataFrame:
    """One row per ordering app."""
    return (lines.select("app_name").distinct()
            .withColumn("is_test_app", F.col("app_name").isin(rules["test_data"]["excluded_apps"])))
def dim_date(spark: SparkSession, lines: DataFrame, silver_dates: DataFrame, rules: dict) -> DataFrame:
    """Every date from 1 Jan of the first order year to 31 Dec of the last; holidays where the source has them."""
    bounds = lines.agg(F.year(F.min("business_date")).alias("y0"), F.year(F.max("business_date")).alias("y1")).first()
    days = spark.sql(f"SELECT explode(sequence(DATE'{bounds.y0}-01-01', DATE'{bounds.y1}-12-31')) AS date")
    iso_dow = ((F.dayofweek("date") + 5) % 7) + 1                      # Monday = 1 … Sunday = 7
    scope = rules["reporting_scope"]
    holidays = silver_dates.select("date", "is_holiday", "holiday_name")
    return (days
            .withColumn("year", F.year("date"))
            .withColumn("quarter", F.quarter("date"))
            .withColumn("month", F.month("date"))
            .withColumn("month_name", F.date_format("date", "MMMM"))
            .withColumn("iso_year", F.year(F.date_add("date", 4 - iso_dow)))   # the year of the week's Thursday
            .withColumn("iso_week", F.weekofyear("date"))
            .withColumn("day_of_week", F.date_format("date", "EEEE"))
            .withColumn("day_of_week_num", iso_dow)
            .withColumn("is_weekend", iso_dow >= 6)
            .join(holidays, "date", "left")                                 # NULL = unknown outside the source
            .withColumn("is_in_scope", F.col("date").between(F.lit(str(scope["start_date"])).cast("date"),
                                                             F.lit(str(scope["end_date"])).cast("date"))))
