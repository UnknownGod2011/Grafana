# StageGuard

**Production-oriented incident commander for live media workflows.**

StageGuard is a personal open-source project that uses Grafana as its operational evidence plane and is designed to use Gemini / Google Cloud for higher-level orchestration and explanation. It investigates live-production failures through Grafana MCP, correlates bounded evidence, requests explicit approval for consequential remediation, verifies recovery from telemetry, and preserves an incident audit trail.

> Product thesis: **Grafana gives the agent trustworthy operational evidence; StageGuard turns that evidence into bounded decisions and actions; Grafana then proves whether recovery actually happened.**

## Current executable vertical slice

```text
deterministic broadcast simulator
  → Prometheus
  → Grafana
  → official grafana/mcp-grafana
  → McpPrometheusMetricClient
  → bounded four-evidence investigator
  → IncidentService
  → explicit revision-bound human approval
  → separate remediation adapter
  → telemetry-only recovery verification
  → append-only audit record
```

The local fixture models three camera feeds and two uplinks. The seeded incident is deliberately specific: `cam-3` drops frames because `uplink-b` has severe packet loss while encoder CPU/GPU and peer feeds remain healthy.

## Why this product exists

Live broadcasts, virtual productions, sports streams, creator studios, and media pipelines fail under severe time pressure. Operators often already have the telemetry required to solve an incident, but the diagnosis still requires manually correlating metrics, logs, traces, alerts, dashboards, and topology while viewers experience the outage.

StageGuard is intended to shorten that loop without becoming an unconstrained infrastructure agent. The core questions are:

1. What broke?
2. What evidence supports that diagnosis?
3. What else is affected?
4. What action is safe and authorized?
5. Did the action actually restore service?

## Safety model

StageGuard keeps observation and action structurally separate.

| Boundary | Policy |
|---|---|
| Grafana / MCP | Read-only evidence plane with least-privilege credentials |
| Investigation | Fixed/bounded evidence contracts; missing evidence causes abstention |
| Approval | Explicit human approval bound to the exact incident + evidence revision |
| Remediation | Separate write-capable adapter; no arbitrary action names from callers |
| Recovery | Action success is never recovery; Grafana/Prometheus telemetry must prove health |
| Audit | Lifecycle events are appended; approvals are single-use and stale approvals are rejected |

The current incident investigator performs exactly six PromQL reads covering symptom, causal signal, contradiction evidence, and healthy-peer evidence. It emits `abstain` rather than allowing Gemini or another LLM to invent missing operational evidence.

## Narrow incident API

`runtime/api.py` exposes only the deterministic lifecycle:

- `GET /healthz`
- `GET /v1/incident`
- `POST /v1/investigate`
- `POST /v1/approve`
- `POST /v1/execute`

The API deliberately does **not** accept PromQL, datasource identifiers, arbitrary remediation action names, or arbitrary targets. Approval requires the exact `incident_id` and evidence `revision`, preventing authorization from being replayed after a fresh investigation changes the evidence.

## Local runtime

Start the simulator, Prometheus, and Grafana:

```bash
docker compose up --build -d
```

Useful local endpoints:

- simulator metrics: `http://localhost:9108/metrics`
- simulator state: `http://localhost:9108/state`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

Bootstrap the least-privilege local Grafana MCP service-account credential:

```bash
python runtime/bootstrap_grafana.py
```

Then prove a real official-MCP metric read:

```bash
python runtime/mcp_smoke.py
```

The MCP Compose profile is opt-in and constrained to read-only datasource/Prometheus capabilities. Secrets are stored under a gitignored local secrets directory and are not printed by the bootstrap path.

See [`runtime/README.md`](runtime/README.md) for the complete local workflow and the current MCP contract.

## Real-user integration direction

StageGuard should work with Grafana Cloud or self-hosted Grafana without forcing teams to rename their telemetry. Production onboarding is intended to support configurable mappings from existing labels/datasources into a small canonical model such as `production`, `service`, `device`, `feed`, `region`, and `severity`.

Real deployments should provide:

- a least-privilege Grafana/MCP identity;
- separate credentials for each allowlisted remediation adapter;
- production-specific telemetry mappings;
- explicit approval policy;
- durable/immutable audit persistence;
- authenticated operator UI/API access;
- a dry-run readiness check before write capabilities are enabled.

## Repository structure

- `runtime/simulator.py` — deterministic media telemetry and controlled fault/recovery fixture
- `runtime/investigator.py` — bounded incident evidence policy
- `runtime/mcp_metric_client.py` — official Grafana MCP → metric client adapter
- `runtime/remediation.py` — approval-gated action + telemetry recovery verification
- `runtime/incident_service.py` — lifecycle orchestration and append-only audit boundary
- `runtime/api.py` — narrow local HTTP API
- `runtime/tests/` — deterministic policy/service tests
- `runtime/grafana/`, `runtime/prometheus/` — local observability provisioning
- `ARCHITECTURE.md` — architecture and trust-boundary detail
- `progress.md` — exact implementation/run log and next step

## Tests

The deterministic Python tests intentionally avoid paid services and API keys:

```bash
python -m unittest discover -s runtime/tests -v
python -m py_compile runtime/*.py
```

The full Docker → Grafana → official MCP gate still requires a Docker-capable host. Missing cloud/Gemini credentials do not block local implementation or safety testing.

## Near-term roadmap

The next implementation priorities are:

1. execute the complete local official-MCP diagnosis/remediation/recovery path on a Docker-capable host and capture real latency/tool traces;
2. add authenticated operator identity and durable audit persistence suitable for deployment;
3. add Loki corroboration and configurable telemetry mappings;
4. place Gemini above the deterministic safety core for incident summarization, hypothesis workflow selection, operator communication, and bounded tool orchestration;
5. build the operator incident console and deployment path on Google Cloud.

## Official references

- Grafana MCP introduction: https://grafana.com/docs/grafana/latest/developer-resources/mcp/introduction/
- Grafana MCP authentication: https://grafana.com/docs/grafana/latest/developer-resources/mcp/configure/authentication/
- Grafana MCP tool restriction: https://grafana.com/docs/grafana/latest/developer-resources/mcp/configure/enable-and-disable-tools/
- Official Grafana MCP repository: https://github.com/grafana/mcp-grafana
- Grafana MCP Observability: https://grafana.com/docs/grafana-cloud/observe-and-act/monitor-applications/ai-observability/mcp-observability/
- Gemini Enterprise Agent Platform Runtime quickstart: https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime/quickstart-adk

## Project status

StageGuard is under active development as a personal open-source project. The deterministic local incident lifecycle is now implemented through investigation, evidence-revision-bound approval, remediation, telemetry-based recovery verification, and append-only audit logging. The major unproven integration gate remains executing that lifecycle through a live `grafana/mcp-grafana:1.1.0` process on a Docker-capable host.
