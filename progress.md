# StageGuard Progress

## Current status

StageGuard is a personal open-source project with an executable local telemetry slice and a deterministic bounded incident-investigation core. Current vertical slice:

`deterministic simulator → Prometheus → Grafana → official Grafana MCP → bounded four-evidence investigator`

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

---

## Run log — 2026-09-06 — bounded incident investigator

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected repository root, `runtime/`, `runtime/tests/`, `runtime/simulator.py`, `runtime/mcp_smoke.py`, and `runtime/README.md`. Rechecked the official `grafana/mcp-grafana` Prometheus tool implementation and confirmed that `query_prometheus` returns a structured `QueryPrometheusResult` containing `data`, optional `hints`, and warnings; its MCP tool is explicitly annotated read-only/idempotent.

Official source checked:

- https://github.com/grafana/mcp-grafana/blob/main/tools/prometheus.go

### Exact changes made

Added `runtime/investigator.py`:

- introduces a minimal read-only `MetricQueryClient.instant(promql)` boundary;
- executes exactly six fixed PromQL reads covering the four required evidence classes;
- encodes thresholds for Camera 3 dropped frames, `uplink-b` packet loss, encoder CPU/GPU contradiction evidence, and healthy peer evidence;
- emits one of `diagnosed`, `no_incident`, or `abstain`;
- returns structured evidence including query, observed value, threshold, and whether it supports the hypothesis;
- refuses to diagnose when any required evidence class is unavailable;
- refuses to diagnose when a real symptom exists but the causal/contradiction/peer evidence does not support the fixed hypothesis.

Added `runtime/tests/test_investigator.py` with six cases:

1. successful four-evidence `uplink-b packet loss` diagnosis;
2. missing causal telemetry forces abstention;
3. one missing GPU contradiction metric marks the entire contradiction evidence class missing;
4. elevated symptom with normal `uplink-b` packet loss abstains;
5. healthy Camera 3 returns `no_incident`;
6. the investigator remains bounded to exactly six reads.

Updated `runtime/README.md` to document the policy boundary, six evidence queries, abstention invariant, test coverage, and the correct next integration step.

### Tests/results

A direct repository clone/test run was attempted in the execution container, but outbound DNS to `github.com` is unavailable there, so the clone failed before tests could execute. No false passing result is recorded. The new tests are committed and require only the Python standard library; they should be run on the next Docker/network-capable host with:

```text
python -m unittest discover -s runtime/tests -v
python -m py_compile runtime/bootstrap_grafana.py runtime/mcp_smoke.py runtime/investigator.py
```

### Decisions made

1. Keep safety-critical evidence completeness deterministic rather than delegating it to Gemini.
2. Keep the investigator transport-agnostic until a real `mcp-grafana:1.1.0` `query_prometheus` payload is captured; do not guess the serialization shape.
3. Use a fixed query budget for the first vertical slice so evidence provenance, latency, and failure behavior are measurable.
4. Treat an observed symptom with unsupported root-cause evidence as abstention rather than downgrading to a speculative diagnosis.

### Current blockers / unknowns

- Full Compose startup and Gate A remain unverified on a Docker-capable host.
- The exact MCP JSON-RPC content/structured-content envelope emitted by the pinned server has not been captured against this stack.
- The new investigator test suite has not yet been executed in this automation environment because its container cannot resolve GitHub and has no repository checkout.
- Gemini orchestration, Loki corroboration, approval/remediation, recovery verification, dashboard/UI, and external-user telemetry mappings remain future implementation gates.

## Single best next step

**Execute Gate A on a Docker-capable host and capture the real `query_prometheus` response envelope from `grafana/mcp-grafana:1.1.0`; then implement a small `McpPrometheusMetricClient` adapter into `MetricQueryClient.instant`, run the six investigator tests plus one real MCP-backed diagnosis, and record query latency/tool-call provenance.**
