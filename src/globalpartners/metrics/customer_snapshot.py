"""gold.customer_daily_snapshot (spec: docs/03_architecture/Step3_Data_Model.md, section 7).

One row per customer per day, from the customer's first order to the last loaded business day.
Built from gold.fact_order in small pure functions, each adding one group of columns:

    customer_calendar   the dense day list with that day's orders and revenue
    add_totals          to-date totals: orders, revenue (= CLV), recency, average order value
    add_loyalty         loyalty flag of the latest order up to that day
    add_windows         last 90 / last 30 days and the spend trend
    add_clv_tier        cume_dist of CLV among all customers of that day
    add_rfm             R, F, M scores and the segment (fixed bands from config)
    add_churn           active / at_risk / lapsed

Because the calendar is dense (one row per day), "the last N days" is simply the last N rows.
"""
from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F

from globalpartners.metrics.sales import in_sales_scope

CUSTOMER_DAY = ["customer_id"]


def customer_orders(fact_order: DataFrame, rules: dict) -> DataFrame:
    """Orders that count for customer metrics: in the reporting dates, no test data, no non-customer account, no guests."""
    orders = in_sales_scope(fact_order, rules).where(~F.col("is_non_customer_account"))
    if not rules["customers"]["guests_in_customer_metrics"]:
        orders = orders.where(~F.col("is_guest"))
    return orders


def customer_calendar(fact_order: DataFrame, rules: dict) -> DataFrame:
    """One row per customer per day, from their first order to the last loaded business day.

    Days without orders are kept (orders_on_day = 0, revenue_on_day = 0): recency, churn status and
    tiers change on those days too.
    """
    # The last loaded day is the same for every customer; it comes from all sales in scope (guests included).
    last_day = in_sales_scope(fact_order, rules).agg(F.max("business_date")).first()[0]

    orders = customer_orders(fact_order, rules)
    per_day = (orders.groupBy("customer_id", "business_date")
               .agg(F.count(F.lit(1)).alias("orders_on_day"),
                    F.sum("order_revenue").cast("decimal(14,2)").alias("revenue_on_day")))
    first_day = per_day.groupBy("customer_id").agg(F.min("business_date").alias("first_order_date"))

    days = (first_day
            .withColumn("snapshot_date", F.explode(F.sequence(F.col("first_order_date"), F.lit(last_day))))
            .select("snapshot_date", "customer_id", "first_order_date"))

    return (days.join(per_day.withColumnRenamed("business_date", "snapshot_date"),
                      ["snapshot_date", "customer_id"], "left")
            .withColumn("orders_on_day", F.coalesce("orders_on_day", F.lit(0)))
            .withColumn("revenue_on_day", F.coalesce("revenue_on_day", F.lit(0)).cast("decimal(14,2)")))


def _history() -> Window:
    """All days of the customer up to and including this one."""
    return (Window.partitionBy("customer_id").orderBy("snapshot_date")
            .rowsBetween(Window.unboundedPreceding, Window.currentRow))


def _last_days(n: int, offset: int = 0) -> Window:
    """The n days ending `offset` days before this one (dense calendar: one row = one day)."""
    return (Window.partitionBy("customer_id").orderBy("snapshot_date")
            .rowsBetween(-(n - 1 + offset), -offset))


def add_totals(cal: DataFrame) -> DataFrame:
    """Totals to date. revenue_to_date is the customer lifetime value (CLV) on that day."""
    h = _history()
    order_day = F.when(F.col("orders_on_day") > 0, F.col("snapshot_date"))
    return (cal
            .withColumn("orders_to_date", F.sum("orders_on_day").over(h).cast("long"))
            .withColumn("revenue_to_date", F.sum("revenue_on_day").over(h).cast("decimal(14,2)"))
            .withColumn("last_order_date", F.max(order_day).over(h))
            .withColumn("avg_order_value_to_date",
                        (F.col("revenue_to_date") / F.col("orders_to_date")).cast("decimal(14,2)"))
            .withColumn("days_since_first_order", F.datediff("snapshot_date", "first_order_date"))
            .withColumn("days_since_last_order", F.datediff("snapshot_date", "last_order_date"))
            .withColumn("is_repeat_customer", F.col("orders_to_date") >= 2)
            .withColumn("_order_days_to_date", F.sum(F.when(F.col("orders_on_day") > 0, 1).otherwise(0)).over(h))
            # average gap between distinct order days = (last - first) / (order days - 1); NULL with one order day
            .withColumn("avg_days_between_orders",
                        F.when(F.col("_order_days_to_date") > 1,
                               F.datediff("last_order_date", "first_order_date") / (F.col("_order_days_to_date") - 1))
                        .cast("decimal(10,2)"))
            .drop("_order_days_to_date"))


def add_loyalty(cal: DataFrame, fact_order: DataFrame, rules: dict) -> DataFrame:
    """is_loyalty_as_of: the loyalty flag of the customer's latest order up to that day."""
    orders = customer_orders(fact_order, rules)
    # One flag per customer per order day (the latest order of the day wins; ties: loyalty true)
    last_of_day = (orders.groupBy("customer_id", "business_date")
                   .agg(F.max_by("is_loyalty", F.struct("order_ts_local", F.col("is_loyalty").cast("int")))
                        .alias("_flag"))
                   .withColumnRenamed("business_date", "snapshot_date"))
    joined = cal.join(last_of_day, ["snapshot_date", "customer_id"], "left")
    return (joined.withColumn("is_loyalty_as_of", F.last("_flag", ignorenulls=True).over(_history()))
            .drop("_flag"))


def add_windows(cal: DataFrame, rules: dict) -> DataFrame:
    """Frequency and monetary windows (RFM) and the spend trend."""
    n = rules["rfm"]["window_days"]
    t = rules["spend_trend"]["window_days"]
    df = (cal
          .withColumn("orders_last_90d", F.sum("orders_on_day").over(_last_days(n)).cast("long"))
          .withColumn("revenue_last_90d", F.sum("revenue_on_day").over(_last_days(n)).cast("decimal(14,2)"))
          .withColumn("revenue_last_30d", F.sum("revenue_on_day").over(_last_days(t)).cast("decimal(14,2)"))
          .withColumn("revenue_prev_30d", F.sum("revenue_on_day").over(_last_days(t, offset=t)).cast("decimal(14,2)")))
    # the window columns keep their names even if the config uses other lengths; the spec names say 90 / 30
    return (df.withColumn("revenue_prev_30d", F.coalesce("revenue_prev_30d", F.lit(0)).cast("decimal(14,2)"))
            .withColumn("spend_change_pct_30d",
                        F.when(F.col("revenue_prev_30d") > 0,
                               (F.col("revenue_last_30d") - F.col("revenue_prev_30d")) / F.col("revenue_prev_30d") * 100)
                        .cast("decimal(12,2)")))


def add_clv_tier(cal: DataFrame, rules: dict) -> DataFrame:
    """CLV tier: cume_dist of revenue_to_date among all customers of the same day (equal CLV, equal tier)."""
    tiers = rules["clv_tiers"]
    by_clv = Window.partitionBy("snapshot_date").orderBy("revenue_to_date")
    return (cal.withColumn("clv_cume_dist", F.cume_dist().over(by_clv).cast("decimal(10,6)"))
            .withColumn("clv_tier",
                        F.when(F.col("clv_cume_dist") > tiers["high_if_cume_dist_above"], "High")
                        .when(F.col("clv_cume_dist") <= tiers["low_if_cume_dist_at_or_below"], "Low")
                        .otherwise("Medium")))


def _score(column: str, bands: dict, ascending_is_better: bool) -> F.Column:
    """Score 1 to 5 from fixed bands. Recency: smaller is better; frequency and monetary: larger is better."""
    ordered = sorted(bands.items(), key=lambda kv: kv[0], reverse=True)       # best score first
    score = F.lit(1)
    for points, limit in reversed(ordered):                                    # worst band first, best band wins last
        condition = F.col(column) <= limit if ascending_is_better else F.col(column) >= limit
        score = F.when(condition, F.lit(points)).otherwise(score)
    return score


def add_rfm(cal: DataFrame, rules: dict) -> DataFrame:
    """R, F, M scores and the segment (rules are checked top to bottom, first match wins)."""
    cfg = rules["rfm"]
    df = (cal
          .withColumn("r_score", _score("days_since_last_order", cfg["recency_score_if_days_at_most"], True))
          .withColumn("f_score", _score("orders_last_90d", cfg["frequency_score_if_orders_at_least"], False))
          .withColumn("m_score", _score("revenue_last_90d", cfg["monetary_score_if_spend_at_least"], False)))
    segment = F.lit(None).cast("string")
    for rule in reversed(cfg["segments"]):                                     # last rule first, so the first rule wins
        conditions = [F.lit(True)]
        for key, column in (("min_r", "r_score"), ("min_f", "f_score"), ("min_m", "m_score")):
            if key in rule:
                conditions.append(F.col(column) >= rule[key])
        for key, column in (("max_r", "r_score"), ("max_f", "f_score")):
            if key in rule:
                conditions.append(F.col(column) <= rule[key])
        if "max_days_since_first_order" in rule:
            conditions.append(F.col("days_since_first_order") <= rule["max_days_since_first_order"])
        all_true = conditions[0]
        for condition in conditions[1:]:
            all_true = all_true & condition
        segment = F.when(all_true, F.lit(rule["name"])).otherwise(segment)
    return df.withColumn("rfm_segment", segment)


def add_churn(cal: DataFrame, rules: dict) -> DataFrame:
    """active / at_risk / lapsed from the days since the last order."""
    churn = rules["churn"]
    return cal.withColumn(
        "churn_status",
        F.when(F.col("days_since_last_order") <= churn["active_if_days_at_most"], "active")
        .when(F.col("days_since_last_order") <= churn["at_risk_if_days_at_most"], "at_risk")
        .otherwise("lapsed"))


COLUMNS = ["snapshot_date", "customer_id", "orders_on_day", "revenue_on_day",
           "first_order_date", "last_order_date", "orders_to_date", "revenue_to_date", "avg_order_value_to_date",
           "days_since_first_order", "is_repeat_customer", "clv_cume_dist", "clv_tier",
           "days_since_last_order", "avg_days_between_orders", "orders_last_90d", "revenue_last_90d",
           "revenue_last_30d", "revenue_prev_30d", "spend_change_pct_30d",
           "r_score", "f_score", "m_score", "rfm_segment", "churn_status", "is_loyalty_as_of"]


def customer_daily_snapshot(fact_order: DataFrame, rules: dict, run_id: str) -> DataFrame:
    """The whole table: dense calendar, then each group of columns."""
    df = customer_calendar(fact_order, rules)
    df = add_totals(df)
    df = add_loyalty(df, fact_order, rules)
    df = add_windows(df, rules)
    df = add_clv_tier(df, rules)
    df = add_rfm(df, rules)
    df = add_churn(df, rules)
    return (df.select(*COLUMNS)
            .withColumn("_run_id", F.lit(run_id))
            .withColumn("_computed_at", F.current_timestamp()))
