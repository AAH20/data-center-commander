# Video Script: Data Center Commander — Containerization Demo (Docker)

**Target length:** 5–6 minutes  
**Audience:** DevOps engineers, platform engineers, developers  
**Goal:** Demonstrate how Data Center Commander is containerized using a multi-stage Docker build with security hardening, and how to run the full stack with docker-compose.

---

## Scene 1 — Why Containerize (0:00–0:40)

**Visual:** Screen recording of the `Dockerfile` and `docker-compose.yml` in the project root.

**Narration:**
> "Containers give you reproducibility — the same image runs the same way on your laptop, in CI, and in production. Data Center Commander uses a multi-stage Docker build that produces a minimal, secure runtime image. The full stack — API plus PostgreSQL — starts with a single docker-compose command. Let me show you how it's built."

**On-screen text:** "Multi-stage build · Non-root · Distroless-style"

---

## Scene 2 — Build Stage (0:40–1:45)

**Visual:** Screen recording of the `Dockerfile` build stage. Highlight the `python:3.11-slim` base, the virtual environment creation, and the dependency installation.

**Narration:**
> "The build stage uses Python 3.11 slim as the base. Build dependencies — gcc and build-essential — are installed, then removed. A virtual environment is created at `/opt/venv`. The project is installed with the `postgres` and `tracing` extras, which pulls in the PostgreSQL driver and OpenTelemetry support. The result is a self-contained virtual environment with everything the application needs — and nothing it doesn't."

**Action:** Show the `RUN pip install` command with the `[postgres,tracing]` extras.

---

## Scene 3 — Runtime Stage (1:45–3:00)

**Visual:** Screen recording of the `Dockerfile` runtime stage. Highlight the non-root user, the minimal dependencies, the copied virtual environment, and the security configuration.

**Narration:**
> "The runtime stage is where security matters. A new `python:3.11-slim` image is started from scratch. A non-root user `dcc` is created with UID and GID 999. Only two runtime dependencies are installed: `libpq5` for PostgreSQL connectivity and `curl` for the health check. The virtual environment is copied from the build stage — no compiler, no build tools, no package manager.

Application code is copied with `chown=dcc:dcc` so the non-root user owns the files. The container runs as user `dcc`. The root filesystem is read-only. All capabilities are dropped. Privilege escalation is disabled. The seccomp profile is set to the default. Only port 8790 is exposed."

**Action:** Show the `USER dcc` directive, the `securityContext` equivalent in Docker, and the `EXPOSE 8790`.

---

## Scene 4 — Health Check & Entrypoint (3:00–3:45)

**Visual:** Screen recording of the `HEALTHCHECK` and `ENTRYPOINT` directives.

**Narration:**
> "The health check runs `curl` against `/healthz` every 30 seconds with a 5-second timeout and 3 retries. The start period is 10 seconds to give the application time to initialize. The entrypoint runs `scripts/run-local.py` with host `0.0.0.0` and port `8790`. The application refuses non-loopback binds in local development mode — it will not expose itself to the network unless explicitly configured."

**Action:** Show the `HEALTHCHECK` directive and the `ENTRYPOINT` + `CMD` combination.

---

## Scene 5 — Docker Compose (3:45–4:45)

**Visual:** Screen recording of `docker-compose.yml`. Highlight the two services, the volume, the network, and the health check dependency.

**Narration:**
> "The docker-compose file defines two services. The `db` service runs PostgreSQL 16 Alpine with a persistent volume, automatic schema initialization from the `database/schema.sql` and migration files, and a health check using `pg_isready`. The `app` service builds from the Dockerfile, depends on the database being healthy before starting, and exposes port 8790. Both services are on a private bridge network — `dcc-net` — so the database is not accessible from outside the compose stack.

The schema and migrations are mounted as read-only files into the container's initialization directory, so they run automatically on first startup. No manual database setup required."

**Action:** Show the `depends_on` condition, the volume mounts, and the network configuration.

---

## Scene 6 — Build & Run (4:45–5:30)

**Visual:** Terminal recording showing the docker-compose workflow.

**Narration:**
> "Starting the full stack is one command. The first build takes a few minutes — subsequent starts are seconds."

**Action — terminal commands:**
```bash
docker compose up --build
```

**Narration (continued):**
> "The database initializes automatically with the schema and migrations. The application starts once the database reports healthy. The UI is available at `http://127.0.0.1:8790`. To stop, use `docker compose down`. To reset everything, use `docker compose down -v` to remove the database volume."

---

## Scene 7 — Close (5:30–6:00)

**Visual:** Return to the Dockerfile. Fade to the README.

**Narration:**
> "Data Center Commander's container image is minimal, non-root, and secure by default. The multi-stage build eliminates build tools from the runtime. The docker-compose stack includes PostgreSQL with automatic schema initialization. Everything is open source under AGPL-3.0. Build it, run it, and deploy it to your orchestrator of choice."

**On-screen text:** GitHub repo URL · "Dockerfile · docker-compose.yml"

---

## Production notes

- Use screen recordings from the actual `Dockerfile` and `docker-compose.yml`.
- Terminal recordings should use a clean, readable font with syntax highlighting.
- Show actual `docker compose` output — don't just show the commands.
- The multi-stage build diagram should clearly separate build and runtime stages.
- Caption all narration.
