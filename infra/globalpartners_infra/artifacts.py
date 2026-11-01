"""Collect the files AWS needs into infra/build/ when CDK synthesizes (nothing is uploaded here).

build/glue/globalpartners.zip   the pipeline package, for the Glue jobs' --extra-py-files
build/glue/jobs/<job>.py        one script per Glue job
build/glue/files/               config YAMLs + SQL scripts, for --extra-files (land in the job's working dir)
build/mwaa/dags/                the Airflow DAG
build/dashboard/                the Docker build context of the dashboard image: Dockerfile, requirements.txt,
                                .streamlit/ and dashboard/ (nothing else, so no data or lake file can get in)
"""
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]            # infra/globalpartners_infra/ → project root
BUILD = ROOT / "infra" / "build"
CONFIG_FILES = ["config/environments.yaml", "config/business_rules.yaml"]
SQL_FILES = ["sql/01_create_database.sql", "sql/02_create_tables.sql", "sql/03_replay_procedure.sql"]


def zip_package(source: Path, target: Path) -> None:
    """Zip src/globalpartners with fixed timestamps, so an unchanged package gives an identical file
    (CDK then sees nothing new to upload)."""
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(source.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            info = zipfile.ZipInfo(str(path.relative_to(source.parent)), date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            z.writestr(info, path.read_bytes(), zipfile.ZIP_DEFLATED)


def stage_dashboard(target: Path) -> None:
    """The dashboard image's build context (see dashboard/Dockerfile)."""
    code = ROOT / "dashboard"
    target.mkdir(parents=True)
    shutil.copy(code / "Dockerfile", target / "Dockerfile")
    shutil.copy(code / "requirements.txt", target / "requirements.txt")
    shutil.copytree(ROOT / ".streamlit", target / ".streamlit")
    shutil.copytree(code, target / "dashboard",
                    ignore=shutil.ignore_patterns("__pycache__", "Dockerfile", "requirements.txt", "*.pyc"))


def build(jobs: list[str]) -> dict[str, Path]:
    shutil.rmtree(BUILD, ignore_errors=True)
    glue, mwaa = BUILD / "glue", BUILD / "mwaa"
    for folder in (glue / "jobs", glue / "files", mwaa / "dags"):
        folder.mkdir(parents=True)

    zip_package(ROOT / "src" / "globalpartners", glue / "globalpartners.zip")
    for job in jobs:
        shutil.copy(ROOT / "src" / "globalpartners" / "jobs" / f"{job}.py", glue / "jobs" / f"{job}.py")
    for file in CONFIG_FILES + SQL_FILES:
        shutil.copy(ROOT / file, glue / "files" / Path(file).name)

    shutil.copy(ROOT / "dags" / "globalpartners_daily.py", mwaa / "dags" / "globalpartners_daily.py")
    stage_dashboard(BUILD / "dashboard")
    return {"glue": glue, "mwaa": mwaa, "dashboard": BUILD / "dashboard"}
