# StageGuard Progress

## Current status

StageGuard is a personal open-source project with an executable local telemetry slice, official Grafana MCP path, deterministic bounded incident investigator, MCP-to-investigator metric adapter, approval-gated remediation/recovery verification, an audited incident orchestration service, and a narrow HTTP API.

Current vertical slice:

`deterministic simulator → Prometheus → Grafana → official Grafana MCP → McpPrometheusMetricClient → bounded four-evidence investigator → IncidentService → evidence-revision-bound human approval → separate remediation adapter → telemetry recovery verification → append-only audit`

Core safety decisions remain locked:

- Grafana is the read-only evidence plane.
- Consequential writes use separate credentials/adapters.
- Missing required evidence causes abstention.
- Callers cannot submit arbitrary PromQL or arbitrary remediation actions through the incident API.
- Human approval must match the exact current incident evidence revision.
- Approval is single-use and is invalidated by a fresh investigation.
- An action API success never counts as recovery.
- Recovery requires multiple consecutive healthy telemetry samples.
- Real-user onboarding must support existing telemetry through mappings rather than forcing metric renames.

---

## Completed runtime milestones

### 2026-09-06 — executable telemetry slice

Added deterministic broadcast simulator, Prometheus scrape configuration, provisioned Grafana datasource UID `stageguard-prometheus`, Docker Compose stack, local runtime documentation, and simulator tests. The simulator exposes Camera 3 dropped frames, encoder CPU/GPU, uplink packet loss, output bitrate, scenario state, and fault/recovery controls.

Previously verified on an executable host:

```text
python -m unittest discover -s runtime/tests -v
Ran 3 tests
OK
```

### 2026-09-06 — official Grafana MCP local path

Added `runtime/bootstrap_grafana.py`, `runtime/mcp_smoke.py`, gitignored local secrets, and opt-in official `grafana/mcp-grafana:1.1.0` Compose profile. MCP is constrained with `--disable-write`, `datasource,prometheus` tool categories only, and proxied tools disabled. The bootstrap creates/reuses a Viewer-only service account with a short-lived token and refuses remote bootstrap unless explicitly opted in.

### 2026-09-06 — bounded incident investigator

Added `runtime/investigator.py` and tests. The investigator performs exactly six fixed PromQL reads, requires symptom + causal + contradiction + healthy-peer evidence for diagnosis, returns `no_incident` for a healthy symptom signal, and explicitly abstains on missing or contradictory evidence.

### 2026-09-06 — official MCP metric adapter

Added `runtime/mcp_metric_client.py` and parser/safety tests. The adapter initializes one MCP session, verifies `query_prometheus` is read-only, calls only that tool for the fixed datasource/query contract, parses the pinned v1.1.0 result envelopes, rejects ambiguous/malformed results, distinguishes empty telemetry from tool failure, and records per-query latency/value provenance.

### 2026-09-06 — approval-gated remediation and recovery verification

Added `runtime/remediation.py` and deterministic tests. The write-capable `RemediationClient` boundary is separate from Grafana. Remediation requires an exact diagnosed incident and explicit matching approval. Recovery is independently verified from bounded packet-loss + dropped-frame telemetry and requires consecutive healthy samples; missing telemetry resets the healthy streak. The local `SimulatorRemediationClient` refuses non-loopback targets.

Official implementation references retained:

- https://github.com/grafana/mcp-grafana/blob/v1.1.0/tools/prometheus.go
- https://github.com/grafana/mcp-grafana/blob/v1.1.0/tools.go
- https://grafana.com/docs/grafana/latest/developer-resources/mcp/configure/enable-and-disable-tools/
- https://grafana.com/docs/grafana/latest/developer-resources/mcp/configure/authentication/

---

## Run log — 2026-09-06 — audited incident orchestration + narrow API

### Inspected at start

Read `progress.md` completely before choosing work. Inspected:

- `runtime/investigator.py`
- `runtime/remediation.py`
- `runtime/tests/test_remediation.py`
- `runtime/README.md`
- root `README.md`

The previous run's single best next step was still the highest-value unblocked work: compose the deterministic diagnosis/approval/remediation/recovery boundaries into one service with an append-only audit trail and safe API surface.

### Exact changes made

Added `runtime/incident_service.py`:

- introduces `IncidentService` as the lifecycle boundary for investigate → approve → execute → verify;
- creates an incident ID on first investigation and a deterministic SHA-256-derived evidence revision from the complete `IncidentReport`;
- binds approval to both the exact `incident_id` and current evidence `revision`;
- rejects approval for `abstain`/`no_incident` states;
- invalidates any previous approval/outcome whenever a fresh investigation runs;
- makes approvals single-use by refusing a second execution after an outcome exists;
- delegates evidence collection only to the existing fixed `investigate()` function, so the service cannot broaden the six-query PromQL budget;
- delegates consequential action/recovery only to the existing `remediate_and_verify()` policy;
- adds `AuditEvent`, `AuditSink`, deterministic `MemoryAuditLog`, and local `JsonlAuditLog`;
- `JsonlAuditLog` uses append mode, never truncates an existing audit file, creates it with owner-only permissions, fsyncs each event, and stores deterministic JSONL;
- records `investigation_completed`, `remediation_approved`, and `remediation_completed` lifecycle events with monotonically increasing sequence numbers;
- deliberately documents JSONL as a local-development primitive rather than claiming it is an immutable production audit store.

Added `runtime/tests/test_incident_service.py` with deterministic service-level coverage for:

1. full diagnose → approve → act → telemetry-verified recovery lifecycle;
2. stale evidence revision rejection;
3. inability to approve an abstained incident;
4. execution refusal without approval;
5. single-use approval/remediation;
6. fresh investigation invalidating previous approval;
7. JSONL audit re-open preserving existing records instead of truncating them.

Added `runtime/api.py`:

- exposes only `GET /healthz`, `GET /v1/incident`, `POST /v1/investigate`, `POST /v1/approve`, and `POST /v1/execute`;
- does not expose generic PromQL, datasource selection, action names, or remediation targets;
- rejects unexpected JSON fields rather than silently accepting future/untrusted capability expansion;
- limits request bodies to 16 KiB and requires JSON objects for body-bearing calls;
- approval accepts only `incident_id`, `revision`, and `approved_by`;
- returns conflict semantics for invalid lifecycle state and avoids leaking internal transport/credential exceptions;
- sends `Cache-Control: no-store` and `X-Content-Type-Options: nosniff`;
- defaults the server bind to loopback and suppresses default HTTP logging that could accidentally emit operator identifiers.

Refreshed root `README.md`:

- removed the obsolete hackathon-target/restriction framing;
- explicitly describes StageGuard as a personal open-source project;
- documents the actually implemented runtime instead of calling the repo specification-only;
- documents the new trust boundaries and narrow incident API;
- records current local runtime commands, repository structure, tests, real-user integration direction, and near-term roadmap.

### Tests / checks / results

Attempted to clone the updated repository into the execution container and run:

```text
python -m unittest discover -s runtime/tests -v
```

The clone failed before test execution because the container cannot resolve `github.com`:

```text
fatal: unable to access 'https://github.com/UnknownGod2011/Grafana.git/': Could not resolve host: github.com
```

Therefore this run does **not** claim that the new service/API tests passed. No GitHub Actions workflow or noisy CI job was added just to compensate for the environment limitation.

Recommended verification commands on the next executable host:

```bash
python -m unittest discover -s runtime/tests -v
python -m py_compile runtime/*.py
```

Then run the full local stack, construct `IncidentService` with `McpPrometheusMetricClient` + `SimulatorRemediationClient`, and exercise the lifecycle through the HTTP API.

### Decisions made

1. Human authorization is bound to immutable evidence identity (`incident_id` + evidence revision), not merely to an action string.
2. A fresh investigation invalidates old authorization because the evidence may have changed.
3. Approval consumption is one-shot; repeated `/execute` calls cannot repeat the consequential action.
4. The API uses typed lifecycle operations, not generic tool/query passthrough.
5. Audit persistence is append-only in the local reference implementation, but production deployment must replace/augment JSONL with durable access-controlled storage.
6. Gemini remains outside the safety-critical policy boundary; it may later summarize, communicate, and select among explicit workflows, but it cannot bypass evidence/approval/action constraints.

### Current blockers / unknowns

- Full Compose startup and end-to-end Gate A remain unverified on a Docker-capable host.
- The six-query diagnosis and two-query recovery loop have not yet been executed through a live `grafana/mcp-grafana:1.1.0` process.
- The newly added service/API tests have not executed in this automation environment because its container cannot resolve GitHub.
- The HTTP API does not yet authenticate operator identity; loopback-only is the current safe default, and non-loopback production exposure would be unsafe without auth/TLS/reverse-proxy policy.
- JSONL is not an immutable multi-user production audit backend.
- Loki corroboration, configurable telemetry mappings, Gemini orchestration/explanation, operator UI/dashboard, production auth/onboarding, and Google Cloud deployment remain implementation gates.

## Single best next step

**Implement authenticated operator identity for the incident API without introducing a paid dependency: add a small pluggable `IdentityProvider` boundary, a safe local development identity mode, and service/API tests proving that approval identity comes from trusted authentication context rather than an arbitrary `approved_by` request-body string. Keep the API loopback-only by default and refuse non-loopback startup unless an explicit authentication provider is configured.**
