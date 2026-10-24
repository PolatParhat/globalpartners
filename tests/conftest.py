"""Shared test setup: one small local Spark session and the real business rules."""
import os
import sys

import pytest
from pyspark.sql import SparkSession

from globalpartners.common.config import load_business_rules

os.environ["PYSPARK_PYTHON"] = sys.executable          # workers use the same Python as the tests


@pytest.fixture(scope="session")
def spark():
    session = (SparkSession.builder.master("local[1]").appName("unit-tests")
               .config("spark.sql.session.timeZone", "UTC")          # same as the pipeline
               .config("spark.sql.shuffle.partitions", "1")          # tiny data: 1 partition is fastest
               .config("spark.ui.enabled", "false")
               .getOrCreate())
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()


@pytest.fixture(scope="session")
def rules():
    return load_business_rules()
