"""Create a SparkSession configured for the current environment."""
from pyspark.sql import SparkSession

ICEBERG_EXTENSIONS = "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions"


def build_spark(app_name: str, env: dict) -> SparkSession:
    """SparkSession with UTC time and the Iceberg catalog for this environment."""
    catalog = env["catalog"]
    prefix = f"spark.sql.catalog.{catalog['name']}"
    builder = (
        SparkSession.builder.appName(app_name)
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.extensions", ICEBERG_EXTENSIONS)
        .config(prefix, "org.apache.iceberg.spark.SparkCatalog")
        .config(f"{prefix}.type", catalog["type"])
        .config(f"{prefix}.warehouse", catalog["warehouse"])
    )
    if catalog["type"] == "glue":
        builder = builder.config(f"{prefix}.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")
    return builder.getOrCreate()


def jdbc_url(db: dict, database: str | None = None) -> str:
    """JDBC URL for SQL Server; the connection is always encrypted."""
    trust = "true" if db["trust_server_certificate"] else "false"
    return (f"jdbc:sqlserver://{db['host']}:{db['port']};databaseName={database or db['database']};"
            f"encrypt=true;trustServerCertificate={trust}")