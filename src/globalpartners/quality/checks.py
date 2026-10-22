"""Data-quality checks run after every load (decision D, design section 4)."""
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from globalpartners.common.source import read_source


def result(name: str, observed, expected, passed: bool, details: str = "", severity: str = "FAIL") -> dict:
    """One check result. A failed WARN check is reported but does not fail the run."""
    return {"check_name": name, "status": "PASS" if passed else severity,
            "observed": str(observed), "expected": str(expected), "details": details}


def distinct_rows(df: DataFrame, cols: list[str]) -> int:
    return df.select(*cols).distinct().count()


def run_checks(spark: SparkSession, lake: str, db: dict, batch_id: str, rules: dict) -> list[dict]:
    t = lambda name: spark.table(f"{lake}.{name}")
    results = []

    # 1. Nothing lost: source → bronze → silver (+ quarantine)
    source_lines = read_source(spark, db, "SELECT COUNT(*) AS n FROM dbo.order_items").first()["n"]
    source_options = read_source(spark, db, "SELECT COUNT(*) AS n FROM dbo.order_item_options").first()["n"]
    bronze_lines = distinct_rows(t("bronze.order_items"), ["order_id", "lineitem_id"])
    open_q = t("silver.quarantine").where(F.col("status") == "open")
    q_lines = open_q.where(F.col("source_table") == "order_items").count()
    q_options = open_q.where(F.col("source_table") == "order_item_options").count()
    silver_lines = t("silver.order_items").count()
    silver_options = t("silver.order_item_options").count()
    results.append(result("source_lines_reach_bronze", bronze_lines, source_lines, bronze_lines == source_lines,
                          "distinct order lines in bronze = rows in dbo.order_items"))
    results.append(result("bronze_lines_reach_silver", silver_lines + q_lines, bronze_lines,
                          silver_lines + q_lines == bronze_lines, f"silver {silver_lines} + quarantined {q_lines}"))
    results.append(result("source_options_reach_silver", silver_options + q_options, source_options,
                          silver_options + q_options == source_options, f"silver {silver_options} + quarantined {q_options}"))

    # 2. Money ties out
    fact_lines, fact_orders = t("gold.fact_order_line"), t("gold.fact_order")
    line_rev = fact_lines.agg(F.sum("line_revenue")).first()[0]
    order_rev = fact_orders.agg(F.sum("order_revenue")).first()[0]
    results.append(result("revenue_orders_equal_lines", order_rev, line_rev, order_rev == line_rev,
                          "Σ fact_order.order_revenue = Σ fact_order_line.line_revenue"))
    item_rev_gold = fact_lines.agg(F.sum("item_revenue")).first()[0]
    item_rev_silver = t("silver.order_items").agg(F.sum("item_price")).first()[0]
    results.append(result("item_revenue_gold_equals_silver", item_rev_gold, item_rev_silver,
                          item_rev_gold == item_rev_silver, "Σ fact_order_line.item_revenue = Σ silver item_price"))
    results.append(result("every_silver_line_in_gold", fact_lines.count(), silver_lines, fact_lines.count() == silver_lines))

    # 3. Keys unique and never empty
    for table, keys in [("silver.order_items", ["order_id", "lineitem_id"]), ("silver.order_item_options", ["option_key"]),
                        ("gold.fact_order_line", ["order_id", "lineitem_id"]), ("gold.fact_order", ["order_id"])]:
        df = t(table)
        dupes = df.count() - distinct_rows(df, keys)
        nulls = df.where(" OR ".join(f"{k} IS NULL" for k in keys)).count()
        results.append(result(f"unique_keys_{table}", f"{dupes} duplicates, {nulls} empty", "0, 0",
                              dupes == 0 and nulls == 0, ", ".join(keys)))

    # 4. Every fact row finds its dimensions
    for fk, dim, key in [("customer_id", "dim_customer", "customer_id"), ("restaurant_id", "dim_location", "restaurant_id"),
                         ("item_key", "dim_item", "item_key"), ("app_name", "dim_app", "app_name"),
                         ("business_date", "dim_date", "date")]:
        missing = fact_lines.join(t(f"gold.{dim}").select(F.col(key).alias(fk)), fk, "left_anti").count()
        results.append(result(f"fact_lines_find_{dim}", missing, 0, missing == 0, f"fact_order_line.{fk} → {dim}.{key}"))

    # 5. Quarantine rate of this batch
    batch_rows = (t("bronze.order_items").where(F.col("_batch_id") == batch_id).count()
                  + t("bronze.order_item_options").where(F.col("_batch_id") == batch_id).count())
    new_q = t("silver.quarantine").where(F.col("first_seen_batch_id") == batch_id).count()
    rate = new_q / batch_rows if batch_rows else 0.0
    limit = rules["data_quality"]["max_quarantine_rate"]
    results.append(result("quarantine_rate", f"{rate:.4%}", f"<= {limit:.2%}", rate <= limit,
                          f"{new_q} new quarantined rows of {batch_rows} in batch {batch_id}"))

    # 6. Loyalty card present ⇔ loyalty flag (finding 7)
    mismatches = t("silver.order_items").where(F.col("printed_card_number").isNotNull() != F.col("is_loyalty")).count()
    results.append(result("loyalty_card_matches_flag", mismatches, 0, mismatches == 0))

    # 7. Generated calendar agrees with the source calendar
    weeks = t("gold.dim_date").join(t("silver.date_dim").select("date", F.col("iso_week").alias("src")), "date")
    week_mismatch = weeks.where(F.col("iso_week") != F.col("src")).count()
    results.append(result("dim_date_iso_week_matches_source", week_mismatch, 0, week_mismatch == 0))

    # 8. Orphan options in the source (cannot be extracted; reported, not failing)
    orphans = read_source(spark, db, """SELECT COUNT(*) AS n FROM dbo.order_item_options o
        WHERE NOT EXISTS (SELECT 1 FROM dbo.order_items i
                          WHERE i.order_id = o.order_id AND i.lineitem_id = o.lineitem_id)""").first()["n"]
    results.append(result("source_orphan_options", orphans, 0, orphans == 0, "options without a parent line in SQL Server",
                          severity="WARN"))
    return results