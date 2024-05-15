## SDN-Controller – Current Project Status

This repository implements a Zero-Trust SDN architecture with a microservice stack. The goal is to enforce intent-driven network security for Kubernetes workloads using a Ryu-based controller, with FastAPI as the “source of truth,” and full observability.

### What’s implemented so far

- **Project skeleton and orchestration**
  - Root `docker-compose.yml` defines eight services: `zookeeper`, `postgres-db`, `fastapi-api`, `ryu-controller`, `telemetry-collector`, `ml-analytics`, `prometheus`, `grafana`.
  - Named volumes for Postgres and Grafana, shared network `sdn_zt`.

- **FastAPI (IBN) API – source of truth**
  - Files: `fastapi-api/requirements.txt`, `fastapi-api/Dockerfile`, `fastapi-api/app/models.py`, `fastapi-api/app/main.py`.
  - Endpoints:
    - POST `/api/v1/policies` – create a policy (validates with Pydantic, persists to PostgreSQL).
    - GET `/api/v1/policies` – list policies.
  - Models:
    - SQLAlchemy `PolicyDB` table with fields: `id`, `name`, `priority`, `source`, `destination`, `service`, `action`, `status`.
    - Pydantic schemas mirror the declarative policy from the blueprint (Table 2), including `label_selector` and `ip_block` support.
  - Runtime:
    - Uvicorn starts `app.main:app` on port 8000.
    - Uses `DATABASE_URL` (provided by Compose) to connect to Postgres.

- **Ryu Controller – HA + Kubernetes-aware policy enforcement**
  - Files: `ryu-controller/requirements.txt`, `ryu-controller/Dockerfile`, `ryu-controller/ha_manager.py`, `ryu-controller/k8s_watcher.py`, `ryu-controller/zt_controller.py`.
  - High Availability:
    - `kazoo`-based leader election via Zookeeper (`/sdn/controller_election`). Winner sets OpenFlow role MASTER; others stay SLAVE.
  - Kubernetes integration:
    - Watches Pod events; emits custom Ryu events to reconcile policy-to-flows mapping.
  - Policy reconciliation (initial version):
    - Loads ENABLED policies from Postgres (the IBN API’s source of truth).
    - Implements high-priority DENY rules (DROP) between matched source/destination IP sets.
    - Notes: ALLOW path is stubbed for now; focus is DENY as per security overlay model.
  - Baseline coexistence:
    - Installs a very low-priority `NORMAL` rule to keep the CNI’s baseline connectivity (“priority override” model).

- **Observability**
  - `prometheus` with minimal `prometheus/prometheus.yml` (scrapes itself and placeholder metrics on `telemetry-collector:9100`).
  - `grafana` container with persistent volume (no dashboards provisioned yet).

- **Placeholders scaffolded**
  - `telemetry-collector/` and `ml-analytics/` each contain a `Dockerfile` and `requirements.txt` placeholder, to be implemented in later prompts.

### Project structure

```text
.
├── docker-compose.yml
├── fastapi-api/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── __init__.py
│       ├── main.py
│       └── models.py
├── ryu-controller/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── ha_manager.py
│   ├── k8s_watcher.py
│   └── zt_controller.py
├── telemetry-collector/
│   ├── Dockerfile
│   └── requirements.txt
├── ml-analytics/
│   ├── Dockerfile
│   └── requirements.txt
└── prometheus/
    └── prometheus.yml
```

### How to run

Prerequisites: Docker and Docker Compose (v2).

```bash
docker compose up -d --build
```

Services will start in dependency order. First run may take a few minutes while images build and dependencies install.

### Access points (default)

- **FastAPI (docs)**: `http://localhost:8000/docs`
- **Prometheus**: `http://localhost:9090`
- **Grafana**: `http://localhost:3000` (default credentials `admin`/`admin` unless overridden)
- **PostgreSQL**: `localhost:5432` (`sdn_policy_db`, user `sdn_user`)
- **Zookeeper**: `localhost:2181`

### Configuration and environment

- `fastapi-api` uses `DATABASE_URL` from Compose: `postgresql://sdn_user:sdn_password@postgres-db/sdn_policy_db`.
- `ryu-controller` uses the same database URL (defaults internally if not set) and connects to Zookeeper at `zookeeper:2181`.

### Current limitations

- Policy enforcement implements the DENY path; ALLOW is not yet implemented.
- `telemetry-collector` and `ml-analytics` are placeholders pending later prompts.
- Kubernetes watcher expects in-cluster config when running inside K8s; for local runs it falls back to `kubeconfig` on the host.

### Next steps (from the blueprint)

- Extend policy translation to include L4 protocol/port matching and ALLOW logic.
- Implement `telemetry-collector` (sFlow + gNMI ingestion and Prometheus metrics).
- Implement `ml-analytics` with Isolation Forest and feedback loop via the IBN API.
- Provision Grafana dashboards and expand Prometheus targets.
- Add Mininet scripts for validation and benchmarking.

### References

- Architectural details and rationale are captured in `builds.md` (the blueprint). This README summarizes the components implemented to date and how to run them. 


