"""Load environment settings and business rules from the config/ folder."""
import os
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"   # src/globalpartners/common/ → project root
ENVIRONMENTS = ("local", "prod")


def pipeline_env() -> str:
    """Return the current environment name from PIPELINE_ENV (default: local)."""
    env = os.environ.get("PIPELINE_ENV", "local")
    if env not in ENVIRONMENTS:
        raise ValueError(f"PIPELINE_ENV must be one of {ENVIRONMENTS}, got {env!r}")
    return env


def load_environment(env: str | None = None) -> dict:
    """Settings for one environment from config/environments.yaml."""
    with open(CONFIG_DIR / "environments.yaml") as f:
        return yaml.safe_load(f)[env or pipeline_env()]


def load_business_rules() -> dict:
    """Business rules from config/business_rules.yaml."""
    with open(CONFIG_DIR / "business_rules.yaml") as f:
        return yaml.safe_load(f)
