# StageGuard Progress

## Current status

StageGuard is a personal open-source project with an executable local telemetry slice. Current vertical-slice target:

`deterministic simulator → Prometheus → Grafana → official Grafana MCP → bounded incident agent`

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

Read `progress.md` completely, inspected the repository root, and reread the fixed `broadcast-alpha` evidence contract before implementation.

### Meaningful implementation progress

Added:

- `runtime/simulator.py`
- `runtime/tests/test_simulator.py`
- `runtime/Dockerfile`
- `runtime/prometheus.yml`
- provisioned Grafana Prometheus datasource UID `stageguard-prometheus`
- `docker-compose.yml`
- `runtime/README.md`

### Tests/results

```text
python -m unittest discover -s runtime/tests -v
Ran 3 tests
OK
```

Docker/Grafana container startup was not executed in that environment.

---

## Run log — 2026-09-06 — official Grafana MCP local integration path

### Inspected at start

Read `progress.md` completely and inspected the repository root, `runtime/`, `docker-compose.yml`, `runtime/README.md`, and the simulator metric labels. Rechecked current official Grafana MCP/service-account documentation before changing the runtime.

### Meaningful implementation progress

Added a reproducible, least-privilege local MCP path:

- `runtime/bootstrap_grafana.py` — zero-dependency, idempotent local bootstrap for a `stageguard-mcp` Viewer service account and short-lived token.
- `runtime/mcp_smoke.py` — zero-dependency MCP stdio client that performs `initialize`, `tools/list`, `list_datasources`, and a real `query_prometheus` call.
- `.gitignore` — excludes `runtime/.secrets/`, Python caches, and local env files.
- `docker-compose.yml` — adds an opt-in `mcp` profile using official `grafana/mcp-grafana:1.1.0` with `--disable-write`, only `datasource,prometheus` categories, and proxied tools disabled.
- `runtime/README.md` — documents bootstrap, secret handling, Gate A smoke test, overrides, and expected `uplink-b` result.

The smoke query is intentionally simple and deterministic:

```promql
network_packet_loss_percent{production_id="broadcast-alpha",uplink="uplink-b"}
```

With the seeded fault active, expected value is approximately `18`.

### Security decisions

1. The normal `docker compose up` does not start MCP; it is an explicit profile/run target.
2. The credential bootstrap refuses remote Grafana hosts unless `STAGEGUARD_ALLOW_REMOTE_BOOTSTRAP=1` is explicitly set.
3. The bootstrap never auto-promotes an existing account; it requires an enabled Viewer.
4. Tokens default to 24-hour TTL and are stored only in a gitignored file with owner-only permissions.
5. MCP consumes the token through `GRAFANA_SERVICE_ACCOUNT_TOKEN_FILE`; the token is not embedded in compose YAML or CLI arguments.
6. MCP is read-only at both credential-role and tool-surface levels for the local evidence gate.

### Research decisions verified against current official sources

- Grafana MCP supports `--disable-write`; Prometheus reads remain available in that mode.
- Tool categories can be narrowed with `--enabled-tools`; `datasource,prometheus` is sufficient for this gate.
- `query_prometheus` requires datasource UID + PromQL and supports instant queries with `endTime="now"`.
- Grafana service-account tokens are the current API authentication mechanism; the HTTP API supports creating/searching service accounts and issuing expiring tokens.
- `GRAFANA_SERVICE_ACCOUNT_TOKEN_FILE` is supported and reread on requests, which is preferable to placing a token inline.

Useful current references:

- https://grafana.com/docs/grafana/latest/developer-resources/mcp/configure/enable-and-disable-tools/
- https://grafana.com/docs/grafana/latest/developer-resources/mcp/configure/authentication/
- https://grafana.com/docs/grafana/latest/developer-resources/mcp/reference/mcp-tools-table/
- https://grafana.com/docs/grafana/latest/developer-resources/api-reference/http-api/api-legacy/serviceaccount/
- https://github.com/grafana/mcp-grafana/releases/tag/v1.1.0

### Tests/results

Executed syntax validation on both new Python utilities before committing:

```text
python -m py_compile runtime/bootstrap_grafana.py runtime/mcp_smoke.py
# success
```

A real Docker/Grafana/MCP call could not be executed from the automation environment because it has no reachable Docker daemon/networked clone. Therefore Gate A is implementation-ready but not yet truthfully marked passed.

### Current blockers / unknowns

- Full compose startup is still unverified on a Docker-capable host.
- The actual `query_prometheus` response payload from `mcp-grafana:1.1.0` has not yet been captured against this stack.
- Grafana OSS Viewer is expected to be sufficient for datasource reads, but the runtime smoke test must prove this exact version/configuration; if not, use explicit datasource-scoped RBAC rather than broadening to Editor.
- Gemini/agent orchestration is not implemented yet.
- Loki corroboration, dashboard, approval/remediation, and recovery verification remain later gates.

## Single best next step

**Run the local Gate A exactly as documented: `docker compose up --build -d`, `python runtime/bootstrap_grafana.py`, then `python runtime/mcp_smoke.py`. Capture the actual MCP server version/tool schema/query response and fix any version-specific auth or transport issue. Once that passes, implement the bounded four-evidence investigation agent with explicit abstention when any required evidence class is unavailable.**
