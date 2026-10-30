"""Load environment settings and business rules from the config/ folder."""
import os
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]           # src/globalpartners/common/ → project root
ENVIRONMENTS = ("local", "prod")


def project_file(relative: str) -> Path:
    """A project file such as 'config/business_rules.yaml' or 'sql/01_create_database.sql'.

    Locally it is in the project folder. On AWS Glue the code runs from a zip, and the files are
    delivered with --extra-files into the job's working directory (by file name only).
    """
    for candidate in (PROJECT_ROOT / relative, Path.cwd() / relative, Path.cwd() / Path(relative).name):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"{relative} not found in {PROJECT_ROOT} or {Path.cwd()}")


def pipeline_env() -> str:
    """Return the current environment name from PIPELINE_ENV (default: local)."""
    env = os.environ.get("PIPELINE_ENV", "local")
    if env not in ENVIRONMENTS:
        raise ValueError(f"PIPELINE_ENV must be one of {ENVIRONMENTS}, got {env!r}")
    return env


def _expand(value):
    """Replace ${VAR} in every string with the environment variable's value (AWS names, endpoints)."""
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand(v) for v in value]
    if isinstance(value, str):
        expanded = os.path.expandvars(value)
        if "${" in expanded:
            raise KeyError(f"environment variable missing for {value!r}")
        return expanded
    return value


def load_environment(env: str | None = None) -> dict:
    """Settings for one environment from config/environments.yaml, with ${VAR} filled in."""
    with open(project_file("config/environments.yaml")) as f:
        return _expand(yaml.safe_load(f)[env or pipeline_env()])


def load_business_rules() -> dict:
    """Business rules from config/business_rules.yaml."""
    with open(project_file("config/business_rules.yaml")) as f:
        return yaml.safe_load(f)
