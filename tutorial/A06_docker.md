# Chapter A6: Docker and Docker Compose

**Time:** 2 hours. **Goal:** explain images vs containers, write a Dockerfile, read `docker-compose.yml` and `dashboard/Dockerfile`, and debug a container.

## 1. The idea

A **container** is a process running in an isolated box with its own files, network and packages, sharing the host's kernel. An **image** is the read-only recipe/snapshot a container starts from. Image : container = class : object, or installer : running program.
**Why:** "works on my machine" becomes "works in this image". This project's local stack (SQL Server, Spark/Glue 5.1, Airflow/MWAA, Streamlit) is the same software AWS runs.

## 2. Commands (type each)

```bash
docker run --rm hello-world                       # run a container, remove it afterwards
docker run -it --rm python:3.11-slim python       # interactive Python inside a container
docker ps                                         # running containers (docker ps -a = all)
docker images                                     # local images
docker logs -f <name>                             # follow a container's output
docker exec -it <name> bash                       # open a shell in a running container
docker stop <name> && docker rm <name>
docker system df                                  # disk used; docker system prune cleans up
```

Flags: `-d` detached (background), `-p 8501:8501` publish port host:container, `-v host:container` mount a folder, `-e KEY=value` environment variable, `--name`, `--rm`.

## 3. Dockerfile

Read `dashboard/Dockerfile`:

| Line | Meaning |
|---|---|
| `FROM public.ecr.aws/docker/library/python:3.11-slim` | start from this base image |
| `ENV PYTHONPATH=/app …` | environment variables baked in |
| `WORKDIR /app` | working folder for the next instructions |
| `COPY requirements.txt .` then `RUN pip install -r requirements.txt` | copy then run a command at **build** time |
| `COPY dashboard ./dashboard` | copy app code |
| `USER app` | run as a non-root user (security) |
| `EXPOSE 8501` | documents the port |
| `HEALTHCHECK …` | how Docker (and the load balancer) tests the container |
| `CMD ["streamlit", "run", "dashboard/app.py"]` | the command run when the container starts |

**Layer caching:** every instruction is a layer; Docker reuses unchanged layers. Copy `requirements.txt` and install **before** copying code, so editing code does not reinstall packages. **`.dockerignore`** keeps junk (data, `.git`) out of the build.
**`CMD` vs `ENTRYPOINT`:** ENTRYPOINT is the fixed program, CMD its default arguments.
**Multi-stage builds:** build in one stage, copy only results to a small final image.

**Architecture matters:** an image is built for a CPU type (ARM64 on your M4 and on Fargate Graviton, AMD64 on most servers). The SQL Server container is AMD64 and runs under Rosetta emulation on your Mac, which explains its crashes (`RETAIL ASSERT … timeout or deadlock`) noted in STATUS.md.

## 4. Volumes and networks

- **Volume / bind mount:** data that outlives the container. `mssql-data` (named volume) keeps the SQL Server database; the `spark` service mounts the project folder so code edits appear inside.
- **Network:** containers on the same Compose network reach each other **by service name** (`host: sqlserver` in `config/environments.yaml`), not `localhost`.
- `localhost` inside a container means the container itself.

## 5. Docker Compose

`docker-compose.yml` describes several containers. Services in this project: `sqlserver`, `spark`, `spark-history`, `dashboard`, and the MWAA/Airflow services.

```bash
docker compose up -d sqlserver          # start (and create) one service
docker compose ps
docker compose logs -f spark
docker compose exec spark spark-submit src/globalpartners/jobs/dq_checks.py
docker compose down                     # stop and remove containers (volumes survive); add -v to delete volumes too
docker compose build spark              # rebuild an image
```

Keys to recognize: `image` / `build`, `ports`, `environment` / `env_file`, `volumes`, `depends_on` (start order, not readiness), `healthcheck`, `command`, `restart`.
**`.env`** holds local secrets for Compose (never committed).

## 6. Debugging checklist

| Symptom | Check |
|---|---|
| Container exits immediately | `docker logs <name>`; run the command interactively |
| "port is already allocated" | another process uses the port: `lsof -i :8501` |
| "connection refused" between containers | wrong host (use service name), service not ready, wrong port |
| Changes to code not visible | not mounted; rebuild the image |
| Disk full | `docker system df`, `docker system prune` |
| Docker API 500 error | restart Docker Desktop (seen once in this project) |
| Wrong architecture warnings | `--platform linux/arm64` or `linux/amd64` |

## 7. Security basics

Run as non-root; pin base image versions; keep images small (fewer attack surface); never bake secrets into images (pass via environment/secret managers); scan images (`docker scout`, ECR scanning).

## 8. Where Docker meets AWS

`cdk deploy` builds `dashboard/Dockerfile`, pushes the image to **ECR** (a registry), and **ECS Fargate** runs it behind a load balancer. The load balancer's health check calls Streamlit's `/_stcore/health`. The AWS bug "No module named dashboard" was found only in the cloud image; the fix is tested by loading the page inside the real image.

## 9. Exercises

1. Run `python:3.11-slim`, install `requests` with pip inside, exit, run again: is it still there? (No: containers are disposable.)
2. Write a Dockerfile for a Python script that prints "hello from container", build it (`docker build -t hello .`) and run it.
3. Make a tiny `docker-compose.yml` with a `redis` and a Python service that reaches `redis` by name.
4. Mount a folder with `-v` and edit a file on your Mac while the container reads it.
5. Read `docker-compose.yml`: for the `spark` service explain each key.
6. Break the health check on purpose and watch `docker ps` show `unhealthy`.

## Interview questions

1. Container vs VM? (share the kernel; lighter, faster to start) 2. Image vs container? 3. How do you persist data? 4. How do containers talk to each other? 5. What is a layer; how do you speed up builds? 6. CMD vs ENTRYPOINT? 7. How do you keep secrets out of images? 8. What does a health check do? 9. Why run as non-root? 10. What is a registry (ECR/Docker Hub)?

## Done when

Exercises 1 to 6 are done and you can explain every key of the `spark` service in the compose file.
