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
    - GET `/api/v1/policies` – list all policies.
    - GET `/api/v1/policies/{id}` – retrieve specific policy.
    - PUT `/api/v1/policies/{id}` – update policy.
    - DELETE `/api/v1/policies/{id}` – delete policy.
  - Models:
    - SQLAlchemy `PolicyDB` table with fields: `id`, `name`, `priority`, `source`, `destination`, `service`, `action`, `status`.
    - Pydantic schemas mirror the declarative policy from the blueprint (Table 2), including `label_selector` and `ip_block` support.
  - Runtime:
    - Uvicorn starts `app.main:app` on port 8000.
    - Uses `DATABASE_URL` (provided by Compose) to connect to Postgres.

- **Ryu Controller – HA + Kubernetes-aware policy enforcement**
  - Files: `ryu-controller/requirements.txt`, `ryu-controller/Dockerfile`, `ryu-controller/ha_manager.py`, `ryu-controller/k8s_watcher.py`, `ryu-controller/zt_controller.py`.
  - High Availability:
    - `kazoo`-based leader election via Zookeeper (`/sdn/controller_election`). Multiple Ryu instances (`ryu-controller`, `ryu-controller-2`) participate, but at any time only one is MASTER; others stay SLAVE.
  - Kubernetes integration:
    - Watches Pod events; emits custom Ryu events (`EventK8sPodUpdate`) to reconcile policy-to-flows mapping.
  - Policy reconciliation (event-driven):
    - A background DB watcher emits `EventPolicyUpdate` when ENABLED policies change in Postgres (the IBN API's source of truth).
    - Handlers in the main Ryu event loop keep an in-memory `policy_map` in sync and reconcile flows accordingly.
    - High-priority DENY rules (DROP) are installed between matched source/destination IP sets; ALLOW is still stubbed (focus is DENY as per the security overlay model).
    - **L4 Protocol/Port Matching**: Supports TCP, UDP, ICMP with optional port matching from policy `service` field (Blueprint section 2.7).
    - All Zero-Trust rules are tagged with an OpenFlow cookie so they can be safely purged and re-installed during reconciliation without touching CNI baseline flows.
  - Baseline coexistence:
    - Installs a very low-priority `NORMAL` rule to keep the CNI's baseline connectivity ("priority override" model).

- **Observability**
  - `prometheus` uses `prometheus/prometheus.yml` to scrape:
    - itself (`localhost:9090`)
    - `telemetry-collector:9100` for hybrid telemetry metrics.
  - `grafana` container with:
    - Pre-provisioned Prometheus datasource.
    - Pre-loaded SDN Telemetry Dashboard (sFlow/gNMI metrics).
    - Persistent volume for custom dashboards.

- **Telemetry & ML analytics pipeline**
  - `telemetry-collector/collector.py` exposes Prometheus metrics on port 9100 and:
    - Listens on UDP 6343 for real sFlow datagrams (counting packets as a first step toward full parsing; configurable via `SFLOW_PORT`).
    - Includes a gNMI subscriber stub (to be wired to `pygnmi` and real OpenConfig targets later).
  - `ml-analytics/analytics.py` runs an `IsolationForest` to detect anomalies on synthetic traffic and triggers closed-loop mitigation by POSTing a high-priority `DENY` policy to the FastAPI IBN API.

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
│   ├── requirements.txt
│   └── collector.py
├── ml-analytics/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── analytics.py
├── prometheus/
│   └── prometheus.yml
└── validation/
    └── kube_topo.py
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
- `ml-analytics` uses `API_URL` (defaults to `http://fastapi-api:8000`) to call the IBN API for mitigation.
- `telemetry-collector` exports Prometheus metrics on port `9100`; sFlow (UDP 6343) and gNMI paths are stubbed in this version.

### Current implementation status vs blueprint

**✅ Fully Implemented:**
- Multi-controller HA with Zookeeper election
- PostgreSQL-backed policy source of truth
- Event-driven K8s Pod watching (with graceful fallback)
- Cookie-tagged flow reconciliation
- L4 protocol/port matching (TCP, UDP, ICMP)
- Full CRUD API for policies (POST, GET, PUT, DELETE)
- Grafana dashboard provisioning
- Real sFlow UDP listener (counting datagrams)
- Closed-loop ML mitigation
- Mininet multi-controller validation
- Benchmark test suite

**⚠️ Partially Implemented:**
- ALLOW policies (architecture ready, logic stubbed)
- sFlow feature parsing (listener works, no packet parsing yet)
- gNMI subscriber (stub only)

**📝 Not Implemented (future work):**
- FastAPI authentication/authorization
- PostgreSQL LISTEN/NOTIFY (uses polling instead)
- 3-node Zookeeper ensemble (single-node works for dev)

### Troubleshooting

**Services won't start:**
- Run `docker compose logs <service-name>` to check specific service logs
- Ensure ports 2181, 5432, 6653, 6654, 8000, 9090, 3000 are not in use
- Wait 30s for DB init; FastAPI retries connection 5 times with exponential backoff

**Ryu controller shows "K8s watcher running in stub mode":**
- This is normal if not running in a K8s cluster
- Controller will still enforce `ip_block` policies from Mininet/validation

**HA not working (both controllers show MASTER):**
- Check Zookeeper logs: `docker compose logs zookeeper`
- Verify both controllers connect to same ZK: check `ZK_HOSTS` env var

**Policy not enforced in Mininet:**
- Check Ryu is MASTER: `docker compose logs ryu-controller | grep MASTER`
- Verify policy created: `curl http://localhost:8000/api/v1/policies`
- Check flows in Mininet: `dpctl dump-flows`

**Health check:**
- Run `bash health_check.sh` to verify all services

### Validation and testing

**Mininet Topology**:
- `validation/kube_topo.py`: Multi-controller topology (2 switches, 4 hosts, dual controllers for HA)
- Run: `sudo python validation/kube_topo.py`

**Benchmark Suite**:
- `validation/benchmark_suite.sh`: Automated test suite implementing Blueprint Table 4
- Tests: baseline performance, ZTA overhead, policy enforcement, L4 matching, ML mitigation, HA failover
- Run: `bash validation/benchmark_suite.sh`

### Next steps (remaining from blueprint)

- Implement ALLOW policy logic (currently DENY-only security model).
- Replace telemetry stubs with real sFlow parsing (pysflow) and gNMI subscriptions (pygnmi).
- Wire ML analytics to consume real flow features from telemetry collector.
- Add authentication/authorization to FastAPI (currently open API).
- Deploy 3-node Zookeeper ensemble for production HA.

### References

- Architectural details and rationale are captured in `builds.md` (the blueprint). This README summarizes the components implemented to date and how to run them. 


