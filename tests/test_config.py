"""The config files load and contain what the jobs read."""
from globalpartners.common.config import load_business_rules, load_environment


def test_business_rules_have_every_section():
    rules = load_business_rules()
    for section in ["reporting_scope", "test_data", "customers", "revenue", "clv_tiers",
                    "rfm", "churn", "extract", "data_quality"]:
        assert section in rules


def test_local_environment_loads(monkeypatch):
    monkeypatch.setenv("PIPELINE_ENV", "local")
    env = load_environment()
    assert env["catalog"]["name"] == "lake" and env["source_db"]["host"] == "sqlserver"
