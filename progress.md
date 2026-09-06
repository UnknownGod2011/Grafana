# StageGuard Progress

## Current status

StageGuard is a personal open-source project with an executable local telemetry slice, official Grafana MCP path, deterministic bounded incident investigator, and a concrete MCP-to-investigator metric adapter.

Current vertical slice:

`deterministic simulator → Prometheus → Grafana → official Grafana MCP → McpPrometheusMetricClient → bounded four-evidence investigator`

Core design docs remain authoritative for product/safety intent: `README.md`, `ARCHITECTURE.md`, `DEMO.md`, `VERTICAL_SLICE_SPEC.md`, `INTEGRATION_HANDOFF.md`, and `OPERATIONS_AND_SAFETY.md`.

## Locked product decisions

- Primary use case: live media/broadcast incident response.
- Seeded incident: `cam-3` frame drops caused by `uplink-b` packet loss while encoder CPU/GPU remain healthy.
- High-confidence diagnosis requires symptom, causal, contradiction, and healthy-peer evidence.
- Missing required evidence causes explicit abstention; an LLM must not fill evidence gaps with guesses.
- Grafana is the evidence plane; remediation credentials stay separate.
- Human approval precedes consequential remediation.
- Recovery must be verified from telemetry, not inferred from an action response.
- Real-user onboarding must support existing telemetry through mappings rather than forcing metric renames.

---

## Completed runtime milestones

### 2026-09-06 — executable telemetry slice

Added deterministic broadcast simulator, Prometheus scrape configuration, provisioned Grafana datasource UID `stageguard-prometheus`, Docker Compose stack, local runtime documentation, and simulator tests. The simulator exposes Camera 3 dropped frames, encoder CPU/GPU, uplink packet loss, output bitrate, scenario state, and fault/recovery controls.

Verified at the time:

```text
python -m unittest discover -s runtime/tests -v
Ran 3 tests
OK
```

### 2026-09-06 — official Grafana MCP local path

Added `runtime/bootstrap_grafana.py`, `runtime/mcp_smoke.py`, gitignored local secrets, and opt-in official `grafana/mcp-grafana:1.1.0` Compose profile. MCP is constrained with `--disable-write`, `datasource,prometheus` tool categories only, and proxied tools disabled. The bootstrap creates/reuses a Viewer-only service account with a short-lived token and refuses remote bootstrap unless explicitly opted in.

Syntax validation succeeded for both utilities. Full Docker/Grafana/MCP Gate A remains unexecuted in the automation environment because no Docker daemon/networked clone is reachable.

Useful official references retained:

- https://grafana.com/docs/grafana/latest/developer-resources/mcp/configure/enable-and-disable-tools/
- https://grafana.com/docs/grafana/latest/developer-resources/mcp/configure/authentication/
- https://grafana.com/docs/grafana/latest/developer-resources/mcp/reference/mcp-tools-table/
- https://github.com/grafana/mcp-grafana/releases/tag/v1.1.0

### 2026-09-06 — bounded incident investigator

Added `runtime/investigator.py` and `runtime/tests/test_investigator.py`. The investigator performs exactly six fixed PromQL reads, requires all four evidence classes for diagnosis, returns `no_incident` for a healthy symptom signal, and explicitly abstains on missing or contradictory evidence.

The policy layer remains transport-agnostic and prevents Gemini or any later orchestrator from bypassing evidence-completeness rules.

---

## Run log — 2026-09-06 — official MCP metric adapter

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected the current repository metadata and default branch, `runtime/mcp_smoke.py`, `runtime/investigator.py`, `runtime/tests/test_investigator.py`, and `runtime/README.md`.

Rechecked the pinned official `grafana/mcp-grafana v1.1.0` source rather than assuming a payload format:

- `tools/prometheus.go` defines `QueryPrometheusResult` as `data` plus optional `hints` and `warnings`, and marks `query_prometheus` read-only/idempotent.
- `tools.go` JSON-marshals ordinary tool return values into MCP text content.

Official source inspected:

- https://github.com/grafana/mcp-grafana/blob/v1.1.0/tools/prometheus.go
- https://github.com/grafana/mcp-grafana/blob/v1.1.0/tools.go

### Exact changes made

Added `runtime/mcp_metric_client.py`:

- implements the investigator's `MetricQueryClient.instant(promql)` boundary over official Grafana MCP stdio;
- initializes one MCP session and verifies `query_prometheus` is available with `readOnlyHint=true`;
- calls only `query_prometheus` with the configured Grafana datasource UID, instant query type, and `endTime=now`;
- parses the pinned v1.1.0 MCP text/JSON result while also accepting `structuredContent` defensively for forward compatibility;
- supports Prometheus instant vector and scalar encodings;
- maps a genuinely empty vector to `None` so the investigator abstains on missing evidence;
- rejects tool errors, malformed/non-numeric samples, unsupported shapes, and multi-series results instead of silently guessing;
- records per-query `QueryTrace` values containing PromQL, latency in milliseconds, and observed value;
- exposes context-manager cleanup so the MCP process is closed reliably.

Added `runtime/tests/test_mcp_metric_client.py` with seven parser/safety cases:

1. single vector sample extraction;
2. scalar extraction;
3. empty vector → missing evidence;
4. `structuredContent` compatibility;
5. multiple series fail closed;
6. MCP tool error is not treated as missing/healthy telemetry;
7. malformed numeric values fail closed.

Updated `runtime/README.md` with the new adapter boundary, safety behavior, direct investigator usage example, expanded test command, and the revised next implementation step.

### Tests/results

The new parser tests are deterministic and require only the Python standard library, but this automation environment still does not provide a checked-out repository or Docker daemon. I therefore did not claim an executed pass for the new suite.

The following commands are now the exact verification set for the next Docker/network-capable host:

```text
python -m unittest discover -s runtime/tests -v
python -m py_compile runtime/bootstrap_grafana.py runtime/mcp_smoke.py runtime/mcp_metric_client.py runtime/investigator.py
python runtime/mcp_smoke.py
```

Then run `investigate(McpPrometheusMetricClient())` and inspect six `QueryTrace` records.

### Decisions made

1. The MCP payload adapter is now grounded in the pinned official v1.1.0 source rather than left blocked on a future manual capture.
2. Empty telemetry and protocol/tool failure remain distinct: empty data becomes `None`; tool/protocol failures raise an error.
3. A bounded query that unexpectedly returns multiple series is unsafe and must fail closed rather than select a sample arbitrarily.
4. Transport latency/provenance belongs in the metric adapter, while diagnosis policy remains deterministic in `investigator.py`.
5. Compatibility with MCP `structuredContent` is allowed only as an equivalent transport envelope; it does not broaden accepted Prometheus evidence shapes.

### Current blockers / unknowns

- Full Compose startup and end-to-end Gate A are still unverified on a Docker-capable host.
- The six-query diagnosis has not yet been executed against a live `grafana/mcp-grafana:1.1.0` process and real local Grafana datasource.
- The exact observed latency distribution is unknown until that live run.
- Loki corroboration, Gemini orchestration, human approval/remediation, telemetry-based recovery verification, dashboard/UI, auth/onboarding mappings, and deployment remain future implementation gates.

## Single best next step

**On the next run, implement the human-approved remediation + recovery-verification state machine against the deterministic simulator, keeping remediation credentials/actions separate from Grafana evidence. Build it so approval is mandatory, a successful action response never equals recovery, and recovery is only declared after bounded post-action telemetry proves packet loss and dropped-frame rate returned below thresholds. This work is unblocked even if Docker/Gate A remains unavailable.**
