# StageGuard Progress

## Current status

StageGuard is a personal open-source project with an executable local telemetry slice, official Grafana MCP path, deterministic bounded incident investigator, MCP-to-investigator metric adapter, and approval-gated remediation/recovery verification.

Current vertical slice:

`deterministic simulator → Prometheus → Grafana → official Grafana MCP → McpPrometheusMetricClient → bounded four-evidence investigator → explicit human approval → separate remediation adapter → bounded telemetry recovery verification`

Core design intent remains: Grafana is the read-only evidence plane; consequential writes use separate credentials/adapters; missing evidence causes abstention; and an action API success never counts as recovery.

## Locked product decisions

- Primary use case: live media/broadcast incident response.
- Seeded incident: `cam-3` frame drops caused by `uplink-b` packet loss while encoder CPU/GPU remain healthy.
- High-confidence diagnosis requires symptom, causal, contradiction, and healthy-peer evidence.
- Missing required evidence causes explicit abstention; an LLM must not fill evidence gaps with guesses.
- Grafana is the evidence plane; remediation credentials stay separate.
- Human approval precedes consequential remediation.
- Recovery must be verified from telemetry, not inferred from an action response.
- Recovery requires multiple consecutive healthy samples so one transient datapoint cannot close an incident.
- Real-user onboarding must support existing telemetry through mappings rather than forcing metric renames.

---

## Completed runtime milestones

### 2026-09-06 — executable telemetry slice

Added deterministic broadcast simulator, Prometheus scrape configuration, provisioned Grafana datasource UID `stageguard-prometheus`, Docker Compose stack, local runtime documentation, and simulator tests. The simulator exposes Camera 3 dropped frames, encoder CPU/GPU, uplink packet loss, output bitrate, scenario state, and fault/recovery controls.

Previously verified:

```text
python -m unittest discover -s runtime/tests -v
Ran 3 tests
OK
```

### 2026-09-06 — official Grafana MCP local path

Added `runtime/bootstrap_grafana.py`, `runtime/mcp_smoke.py`, gitignored local secrets, and opt-in official `grafana/mcp-grafana:1.1.0` Compose profile. MCP is constrained with `--disable-write`, `datasource,prometheus` tool categories only, and proxied tools disabled. The bootstrap creates/reuses a Viewer-only service account with a short-lived token and refuses remote bootstrap unless explicitly opted in.

Full Docker/Grafana/MCP Gate A remains unexecuted in the automation environment because no Docker daemon/networked clone is reachable.

### 2026-09-06 — bounded incident investigator

Added `runtime/investigator.py` and tests. The investigator performs exactly six fixed PromQL reads, requires all four evidence classes for diagnosis, returns `no_incident` for a healthy symptom signal, and explicitly abstains on missing or contradictory evidence.

### 2026-09-06 — official MCP metric adapter

Added `runtime/mcp_metric_client.py` and parser/safety tests. The adapter initializes one MCP session, verifies `query_prometheus` is read-only, calls only that tool for the fixed datasource/query contract, parses pinned v1.1.0 response envelopes, rejects ambiguous/malformed results, distinguishes empty telemetry from tool failure, and records per-query latency/value provenance.

Official implementation references retained:

- https://github.com/grafana/mcp-grafana/blob/v1.1.0/tools/prometheus.go
- https://github.com/grafana/mcp-grafana/blob/v1.1.0/tools.go
- https://grafana.com/docs/grafana/latest/developer-resources/mcp/configure/enable-and-disable-tools/
- https://grafana.com/docs/grafana/latest/developer-resources/mcp/configure/authentication/

---

## Run log — 2026-09-06 — approval-gated remediation and recovery verification

### Inspected at start

Read `progress.md` completely. Inspected `runtime/investigator.py`, `runtime/simulator.py`, and the current runtime directory before choosing the next implementation target. The previous run's single best next step was unblocked without Docker: implement mandatory approval, a separate write boundary, and telemetry-only recovery verification.

### Exact changes made

Added `runtime/remediation.py`:

- defines a `RemediationClient` protocol separate from the read-only `MetricQueryClient` evidence boundary;
- defines explicit `Approval`, `ActionResult`, `RecoverySample`, and `RemediationOutcome` records;
- refuses to execute unless the incident is actually `diagnosed`, the hypothesis exactly matches the seeded uplink-loss diagnosis, approval is explicit, the approver identity is non-empty, and action/production/target all match;
- executes exactly one approved `recover_uplink` action;
- never treats `ActionResult.accepted=True` as recovery;
- verifies recovery from exactly two bounded post-action PromQL signals: `uplink-b` packet loss and Camera 3 dropped-frame rate;
- requires both signals to be observable and below threshold for two consecutive samples by default;
- resets the healthy streak on missing/unhealthy telemetry;
- returns `recovery_unverified` and keeps the incident logically open when telemetry does not prove recovery within the bounded window;
- includes a `SimulatorRemediationClient` for the deterministic local demo that can call `/scenario/recover` but deliberately refuses non-loopback targets, preventing this demo adapter from becoming an accidental remote actuator.

Added `runtime/tests/test_remediation.py` with six deterministic policy tests:

1. no action without explicit approval;
2. mismatched target cannot execute;
3. successful action response alone is not recovery;
4. recovery requires consecutive healthy samples;
5. missing telemetry resets the healthy streak;
6. rejected remediation does not trigger recovery queries.

### Tests/results

The tests are standard-library-only, but this automation execution environment still has no checked-out repository/Docker runtime, so this run did not claim an executed test pass.

Verification command for the next executable host:

```text
python -m unittest discover -s runtime/tests -v
python -m py_compile runtime/remediation.py runtime/investigator.py runtime/mcp_metric_client.py
```

Then run the simulator + Prometheus + Grafana/MCP stack, diagnose the seeded incident, build explicit approval, invoke `SimulatorRemediationClient`, and observe that recovery is not returned until both post-action metrics remain healthy for two consecutive polls.

### Decisions made

1. Approval is a deterministic policy object, not free-form LLM text.
2. The write-capable remediation adapter is structurally separate from Grafana/MCP read credentials.
3. Recovery is telemetry-derived and requires a streak, not one point-in-time sample.
4. Missing recovery telemetry is unsafe and resets the healthy streak instead of being interpreted as healthy.
5. The demo write adapter is loopback-only; any real production actuator must be a separate authenticated implementation.

### Current blockers / unknowns

- Full Compose startup and end-to-end Gate A remain unverified on a Docker-capable host.
- The six-query diagnosis and two-query post-action recovery loop have not yet been executed through a live `grafana/mcp-grafana:1.1.0` process.
- The ideal recovery polling interval/window needs measurement against real Prometheus scrape/rate behavior; the current bounded defaults are intentionally conservative scaffolding.
- Loki corroboration, Gemini orchestration/explanation, durable approval/audit persistence, operator UI/dashboard, production auth/onboarding mappings, and cloud deployment remain future implementation gates.

## Single best next step

**Implement a small incident orchestration service/API that composes `investigate()`, explicit approval creation, the remediation state machine, and an append-only audit record. Keep Gemini optional and explanation-only at first. Expose safe read/status endpoints plus an approval endpoint, and ensure the API cannot execute remediation from arbitrary user-supplied action names or PromQL. Add deterministic service-level tests so the full diagnose → approve → act → verify lifecycle works locally without Docker credentials.**
