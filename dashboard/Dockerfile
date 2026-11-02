# The dashboard image that runs on AWS (Amazon ECS Fargate). Small on purpose: Python + Streamlit + pandas + plotly + boto3.
# It has no Spark: in AWS the dashboard reads the gold tables with Amazon Athena (dashboard/data.py).
#
# The build context is NOT the repo root. infra/globalpartners_infra/artifacts.py stages exactly these files into
# infra/build/dashboard/:  Dockerfile, requirements.txt, .streamlit/, dashboard/   (so no data or lake files ever get in).
# `cdk deploy` builds and pushes it; the CPU architecture is ARM64 (cheaper on Fargate, and the same as an Apple-silicon Mac).
FROM public.ecr.aws/docker/library/python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIPELINE_ENV=prod \
    PYTHONPATH=/app
# PYTHONPATH: `streamlit run dashboard/app.py` puts only /app/dashboard on the import path, so
# `from dashboard import data` would fail with ModuleNotFoundError without /app here.

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY .streamlit ./.streamlit
COPY dashboard ./dashboard

RUN useradd --create-home --uid 10001 app
USER app

EXPOSE 8501
# Streamlit's own health endpoint; the load balancer checks the same path
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8501/_stcore/health', timeout=3)"

CMD ["streamlit", "run", "dashboard/app.py"]
