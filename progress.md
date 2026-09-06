# StageGuard Progress

## Current status

StageGuard is a personal open-source project with an executable local telemetry slice, official Grafana MCP path, deterministic bounded incident investigator, MCP-to-investigator metric adapter, approval-gated remediation/recovery verification, audited incident orchestration, and a narrow authenticated HTTP API.

Current vertical slice:

`deterministic simulator → Prometheus → Grafana → official Grafana MCP → McpPrometheusMetricClient → bounded four-evidence investigator → IncidentService → trusted operator identity → evidence-revision-bound human approval → separate remediation adapter → telemetry recovery verification → append-only audit`

Core safety decisions:

- Grafana is the read-only evidence plane.
- Consequential writes use separate credentials/adapters.
- Missing required evidence causes abstention.
- Callers cannot submit arbitrary PromQL, datasource IDs, remediation actions, or targets through the incident API.
- Operator/approver identity comes from an authentication provider, not request JSON.
- Human approval must match the exact current incident evidence revision.
- Approval is single-use and invalidated by a fresh investigation.
- An action API success never counts as recovery.
- Recovery requires multiple consecutive healthy telemetry samples.
- Real-user onboarding must support existing telemetry through mappings rather than forcing metric renames.

## Completed milestones

### 2026-09-06 — executable telemetry slice

Added deterministic broadcast simulator, Prometheus scrape configuration, provisioned Grafana datasource UID `stageguard-prometheus`, Docker Compose stack, local runtime documentation, and simulator tests.

Previously verified on an executable host:

```text
python -m unittest discover -s runtime/tests -v
Ran 3 tests
OK
```

### 2026-09-06 — official Grafana MCP local path

Added `runtime/bootstrap_grafana.py`, `runtime/mcp_smoke.py`, gitignored local secrets, and opt-in official `grafana/mcp-grafana:1.1.0` Compose profile. MCP is constrained with `--disable-write`, `datasource,prometheus` tool categories only, and proxied tools disabled.

### 2026-09-06 — bounded incident investigator

Added `runtime/investigator.py`. The investigator performs exactly six fixed PromQL reads, requires symptom + causal + contradiction + healthy-peer evidence for diagnosis, returns `no_incident` for a healthy symptom signal, and explicitly abstains on missing or contradictory evidence.

### 2026-09-06 — official MCP metric adapter

Added `runtime/mcp_metric_client.py`. The adapter initializes one MCP session, verifies `query_prometheus` is read-only, parses the pinned v1.1.0 result envelopes, rejects ambiguous/malformed results, distinguishes empty telemetry from tool failure, and records per-query latency/value provenance.

### 2026-09-06 — approval-gated remediation and recovery verification

Added `runtime/remediation.py`. The write-capable `RemediationClient` is separate from Grafana. Remediation requires exact diagnosed evidence and matching explicit approval. Recovery is independently verified from bounded packet-loss + dropped-frame telemetry and requires consecutive healthy samples; missing telemetry resets the streak. The local simulator remediation client refuses non-loopback targets.

### 2026-09-06 — audited incident orchestration + narrow API

Added `runtime/incident_service.py` and `runtime/api.py`. `IncidentService` composes investigate → approve → execute → verify with revision-bound, single-use approval and append-only audit events. The API exposes only `healthz`, incident status, investigate, approve, and execute; it accepts no generic tool/query/action passthrough.

## Run log — 2026-09-06 — authenticated operator identity

### Inspected at start

Read `progress.md` completely before choosing work. Inspected the current repository state and then read:

- `runtime/api.py`
- `runtime/incident_service.py`
- `runtime/tests/test_incident_service.py`
- root `README.md`
- `ARCHITECTURE.md`
- `runtime/README.md`

The previous run's best next step was confirmed as the highest-value unblocked production gap: approval identity was still caller-controlled through the `approved_by` request field even though the rest of the approval policy was strict.

### Exact changes made

Added `runtime/identity.py`:

- introduced immutable `OperatorIdentity(subject, provider)`;
- introduced a pluggable `IdentityProvider` protocol;
- added `AuthenticationError` as the narrow authentication failure type;
- added `LocalDevelopmentIdentityProvider`, which uses a process-configured fixed identity and ignores caller headers;
- marked the local provider explicitly development-only;
- added `StaticBearerIdentityProvider` as a zero-dependency explicit provider for controlled deployments;
- bearer tokens are configured by the host process, retained in memory, compared using `hmac.compare_digest`, and never included in StageGuard audit/API output;
- provider construction rejects empty subjects, empty tokens, and empty token maps.

Updated `runtime/api.py`:

- removed caller-controlled `actor` from `/v1/investigate` and `/v1/execute` request bodies;
- removed caller-controlled `approved_by` from `/v1/approve`;
- all lifecycle actors are now derived from `IdentityProvider.authenticate()`;
- `GET /v1/incident` is authenticated while `GET /healthz` remains intentionally unauthenticated for health checks;
- authentication failures return HTTP 401 plus `WWW-Authenticate: Bearer realm="stageguard"`;
- unexpected identity fields are rejected instead of ignored;
- introduced `make_server()` so startup policy can be tested independently;
- loopback startup defaults to fixed local development identity;
- non-loopback binding fails closed when the active provider is development-only;
- an explicit non-development provider is required before StageGuard can bind to `0.0.0.0` or another non-loopback address;
- existing body-size, JSON-type, no-store, nosniff, narrow-endpoint, and internal-error-redaction behavior remains intact.

Added `runtime/tests/test_identity.py` with deterministic coverage for:

1. local fixed identity ignoring attacker-controlled authorization headers;
2. valid bearer token → configured operator subject;
3. missing/basic/invalid bearer credentials being rejected;
4. empty bearer configuration being rejected.

Added `runtime/tests/test_api.py` with API-level coverage for:

1. mutating endpoints requiring authentication and emitting no audit event when unauthorized;
2. investigation audit actor coming from the authenticated provider;
3. body-supplied `approved_by` being rejected;
4. valid approval using the authenticated operator subject in both approval state and audit;
5. `/healthz` remaining unauthenticated;
6. non-loopback startup refusing the development identity before attempting to bind;
7. non-loopback startup allowing an explicitly configured non-development provider.

Refreshed root `README.md`:

- documents trusted identity as part of the executable vertical slice;
- documents the new identity/authorization safety boundary;
- clarifies that lifecycle bodies no longer accept actor/approver fields;
- documents loopback-only development identity and explicit bearer provider behavior;
- updates repository structure, real-deployment requirements, roadmap, and project status.

### Tests / checks / results

Attempted from the execution container:

```text
git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard
python -m unittest discover -s runtime/tests -v
```

The clone failed before test execution because this container cannot resolve `github.com`:

```text
fatal: unable to access 'https://github.com/UnknownGod2011/Grafana.git/': Could not resolve host: github.com
```

Therefore this run does **not** claim that the newly added identity/API tests passed. No GitHub Actions workflow or noisy CI job was introduced as a workaround.

Recommended verification on the next executable host:

```bash
python -m unittest discover -s runtime/tests -v
python -m py_compile runtime/*.py
```

### Decisions made

1. Identity is authentication context, not business payload. Request JSON cannot assert who approved or executed an action.
2. Local development remains frictionless but is structurally constrained to loopback.
3. Non-loopback exposure must be an explicit deployment decision with a non-development authentication provider.
4. Authentication tokens must never become audit actor values; only stable operator subjects are recorded.
5. The dependency-free static bearer provider is a reference deployment primitive, not a claim of complete internet-edge security. Production deployments still require TLS/reverse-proxy/network policy or integration with a stronger identity system.
6. Gemini remains outside the safety-critical identity, evidence, approval, action, and recovery boundaries.

### Current blockers / unknowns

- Full Compose startup and end-to-end official MCP Gate A remain unverified on a Docker-capable host.
- The six-query diagnosis and recovery loop have not yet been executed through a live `grafana/mcp-grafana:1.1.0` process in this environment.
- The newly added identity/API tests have not executed here because the container cannot resolve GitHub.
- `StaticBearerIdentityProvider` is intentionally small; OIDC/IAP/identity-aware reverse-proxy integration is still needed for a polished hosted deployment.
- JSONL is not an immutable multi-user production audit backend.
- Loki corroboration, configurable telemetry mappings, Gemini orchestration/explanation, operator UI/dashboard, production onboarding, and Google Cloud deployment remain implementation gates.

## Single best next step

**Implement configurable telemetry mappings without weakening the bounded investigator: introduce a validated `TelemetryProfile`/query-builder layer that maps a production's existing metric names and label keys into StageGuard's six fixed semantic evidence slots and two recovery checks. Add tests proving tenant/production scoping, safe label-value escaping, rejection of unsafe metric/label identifiers, and unchanged fixed query-count/abstention semantics. This is the highest-value step for making StageGuard usable against real Grafana environments instead of only the seeded fixture.**
