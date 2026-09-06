# StageGuard Progress

## Current status

StageGuard is now a **personal open-source project** and is no longer constrained by the former hackathon implementation-tool restriction. The repository has moved from specification-only into executable implementation.

Current vertical-slice target:

`deterministic simulator → Prometheus → Grafana → official Grafana MCP → agent diagnosis`

Core design docs remain authoritative for product/safety intent: `README.md`, `ARCHITECTURE.md`, `DEMO.md`, `VERTICAL_SLICE_SPEC.md`, `INTEGRATION_HANDOFF.md`, and `OPERATIONS_AND_SAFETY.md`.

## Locked product decisions carried forward

- Primary use case: live media/broadcast incident response.
- Seeded incident: `cam-3` frame drops caused by `uplink-b` packet loss while encoder CPU/GPU remain healthy.
- High-confidence diagnosis requires symptom, causal, contradiction, and healthy-peer evidence.
- Grafana is the evidence plane; remediation credentials stay separate.
- Human approval precedes consequential remediation.
- Recovery must be verified from telemetry, not inferred from an action response.
- Real-user onboarding must support existing telemetry through mappings rather than forcing metric renames.

---

## Run log — 2026-09-06 — first executable runtime slice

### Inspected at start

Read `progress.md` completely, inspected the repository root, and reread `VERTICAL_SLICE_SPEC.md` to preserve the fixed `broadcast-alpha` evidence contract before writing implementation.

### Meaningful implementation progress

Added the first working code/configuration layer:

- `runtime/simulator.py` — zero-dependency deterministic HTTP/Prometheus telemetry simulator
- `runtime/tests/test_simulator.py` — unit tests for fault, healthy/reset, and four-evidence-class fixture behavior
- `runtime/Dockerfile` — minimal simulator container
- `runtime/prometheus.yml` — 2-second scrape configuration
- `runtime/grafana/provisioning/datasources/stageguard.yml` — provisioned Grafana Prometheus datasource with stable UID `stageguard-prometheus`
- `docker-compose.yml` — local simulator + Prometheus + Grafana stack
- `runtime/README.md` — startup, replay, query, and test instructions

The simulator exposes:

- `GET /metrics`
- `GET /healthz`
- `GET /state`
- `POST /scenario/fault`
- `POST /scenario/recover`
- `POST /scenario/reset`

The fault fixture emits the exact core metrics specified earlier: `video_frames_dropped_total`, `encoder_cpu_percent`, `encoder_gpu_percent`, `network_packet_loss_percent`, and `output_bitrate_mbps`, all scoped to `production_id="broadcast-alpha"`.

### Tests/results

Executed locally before committing:

```text
python -m unittest discover -s runtime/tests -v
Ran 3 tests
OK
```

Covered:

1. faulted fixture contains all four evidence classes required for high-confidence diagnosis;
2. healthy fixture has low `uplink-b` loss and no active fault;
3. reset clears state and the incident can be replayed.

Docker/Grafana container startup was not executed in this environment, so image/network/runtime validation remains pending.

### Decisions made this run

1. Start with a zero-third-party-dependency Python simulator so missing API keys cannot block development.
2. Keep the first runtime local/free: no cloud account or paid Grafana service is required.
3. Use a stable datasource UID (`stageguard-prometheus`) so the subsequent MCP/RBAC integration has a deterministic scope target.
4. Start the compose demo faulted by default for fast reproduction, while keeping explicit reset/fault/recover endpoints for evaluation.
5. Do not add CI yet; tests are cheap local commands and the project should avoid noisy Actions usage.

### Current blockers / unknowns

- The Docker Compose stack has not yet been executed end-to-end in a Docker-capable environment.
- Official `grafana/mcp-grafana` is not yet wired to the local Grafana instance.
- No MCP service-account token/RBAC bootstrap exists yet.
- No real MCP `query_prometheus` call has been captured.
- Gemini/agent orchestration is not implemented yet.
- Loki corroboration, dashboard, approval/remediation, and recovery verification remain later gates.

## Single best next step

**Wire the official Grafana MCP to this local runtime and prove a real read-only `query_prometheus` call against datasource UID `stageguard-prometheus`.** Add a reproducible local MCP launch/config path, document minimal auth/RBAC bootstrap, and record the actual tool request/response shape. Only after that succeeds, implement the bounded StageGuard investigation agent over the four evidence classes.
