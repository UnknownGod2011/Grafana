# StageGuard

**Production-oriented Gemini/Google Cloud incident commander for live media workflows, with Grafana as the operational evidence plane.**

StageGuard is a personal open-source project. It investigates live-production failures through Grafana MCP, correlates bounded evidence, requires trusted human authorization for consequential remediation, verifies recovery from telemetry, and preserves an incident audit trail.

> **Grafana gives the agent trustworthy operational evidence; StageGuard turns that evidence into bounded decisions and actions; Grafana then proves whether recovery actually happened.**

## Current executable vertical slice

```text
deterministic broadcast simulator
  → Prometheus
  → Grafana
  → official grafana/mcp-grafana
  → McpPrometheusMetricClient
  → bounded four-evidence investigator
  → IncidentService
  → authenticated operator identity
  → evidence-revision-bound human approval
  → separate remediation adapter
  → telemetry-only recovery verification
  → append-only audit record
```

The local fixture models three camera feeds and two uplinks. The seeded incident is deliberately specific: `cam-3` drops frames because `uplink-b` has severe packet loss while encoder CPU/GPU and peer feeds remain healthy.

## Safety model

StageGuard keeps observation, authorization, and action structurally separate.

| Boundary | Policy |
|---|---|
| Grafana / MCP | Read-only evidence plane with least-privilege credentials |
| Investigation | Fixed/bounded evidence contracts; missing evidence causes abstention |
| Identity | Operator identity comes from a configured authentication provider, never request JSON |
| Approval | Explicit approval bound to exact incident + evidence revision; approval is single-use |
| Remediation | Separate write-capable adapter; no arbitrary action names/targets from callers |
| Recovery | Action success is never recovery; Grafana/Prometheus telemetry must prove health |
| Audit | Lifecycle events are appended with the trusted actor identity |

The current investigator performs exactly six PromQL reads covering symptom, causal signal, contradiction evidence, and healthy-peer evidence. It emits `abstain` instead of allowing Gemini or another LLM to invent missing operational evidence.

## Authenticated incident API

`runtime/api.py` exposes only:

- `GET /healthz`
- `GET /v1/incident`
- `POST /v1/investigate`
- `POST /v1/approve`
- `POST /v1/execute`

No endpoint accepts PromQL, datasource identifiers, remediation action names, remediation targets, `actor`, or `approved_by`. The authenticated identity is resolved by `runtime/identity.py` and passed into the service/audit boundary.

Local development uses `LocalDevelopmentIdentityProvider`, a fixed process-configured identity that is safe only on loopback. StageGuard refuses a non-loopback bind when that development provider is active. `StaticBearerIdentityProvider` is a dependency-free explicit provider for controlled deployments (normally behind TLS/reverse-proxy policy); its token-to-subject mapping is supplied by the host process and credentials are never written to audit events or API responses.

## Local runtime

Start the simulator, Prometheus, and Grafana:

```bash
docker compose up --build -d
```

Useful endpoints:

- simulator metrics: `http://localhost:9108/metrics`
- simulator state: `http://localhost:9108/state`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

Bootstrap the least-privilege local Grafana MCP credential:

```bash
python runtime/bootstrap_grafana.py
```

Then prove a real official-MCP metric read:

```bash
python runtime/mcp_smoke.py
```

The MCP Compose profile is opt-in and constrained to read-only datasource/Prometheus capabilities. Secrets live under a gitignored local secrets directory and are not printed by the bootstrap path.

See [`runtime/README.md`](runtime/README.md) for the detailed local workflow and MCP contract.

## Real-user integration direction

StageGuard should work with Grafana Cloud or self-hosted Grafana without forcing teams to rename telemetry. Production onboarding should support configurable mappings from existing labels/datasources into a small canonical model such as `production`, `service`, `device`, `feed`, `region`, and `severity`.

A production deployment should provide least-privilege Grafana/MCP access, a real operator authentication provider, separate credentials per allowlisted remediation adapter, production-specific telemetry mappings, durable tamper-resistant audit storage, TLS/reverse-proxy policy, and a dry-run readiness check before write capabilities are enabled.

## Repository structure

- `runtime/simulator.py` — deterministic media telemetry and controlled fault/recovery fixture
- `runtime/investigator.py` — bounded incident evidence policy
- `runtime/mcp_metric_client.py` — official Grafana MCP → metric client adapter
- `runtime/remediation.py` — approval-gated action + telemetry recovery verification
- `runtime/incident_service.py` — lifecycle orchestration and append-only audit boundary
- `runtime/identity.py` — pluggable trusted operator identity providers
- `runtime/api.py` — narrow authenticated HTTP API
- `runtime/tests/` — deterministic policy/service/API tests
- `runtime/grafana/`, `runtime/prometheus/` — local observability provisioning
- `ARCHITECTURE.md` — architecture and trust-boundary detail
- `progress.md` — exact implementation/run log and next step

## Tests

The deterministic Python tests intentionally avoid paid services and API keys:

```bash
python -m unittest discover -s runtime/tests -v
python -m py_compile runtime/*.py
```

The Docker → Grafana → official MCP gate still requires a Docker-capable host. Missing cloud/Gemini credentials do not block local implementation or safety testing.

## Near-term roadmap

1. execute the complete official-MCP diagnosis/remediation/recovery path on a Docker-capable host and capture real latency/tool traces;
2. add configurable telemetry/property mappings so real productions can use existing metric names/labels;
3. add Loki corroboration and evidence provenance across metrics + logs;
4. place Gemini above the deterministic safety core for incident summarization, bounded workflow selection, and operator communication;
5. build the authenticated operator incident console and durable audit/deployment path on Google Cloud.

## Official references

- Grafana MCP introduction: https://grafana.com/docs/grafana/latest/developer-resources/mcp/introduction/
- Grafana MCP authentication: https://grafana.com/docs/grafana/latest/developer-resources/mcp/configure/authentication/
- Grafana MCP tool restriction: https://grafana.com/docs/grafana/latest/developer-resources/mcp/configure/enable-and-disable-tools/
- Official Grafana MCP repository: https://github.com/grafana/mcp-grafana
- Grafana MCP Observability: https://grafana.com/docs/grafana-cloud/observe-and-act/monitor-applications/ai-observability/mcp-observability/
- Gemini Enterprise Agent Platform Runtime quickstart: https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime/quickstart-adk

## Project status

StageGuard is under active development. The deterministic local incident lifecycle is implemented through investigation, authenticated evidence-revision-bound approval, remediation, telemetry-based recovery verification, and append-only audit logging. The major unproven integration gate remains executing that lifecycle through a live `grafana/mcp-grafana:1.1.0` process on a Docker-capable host.
