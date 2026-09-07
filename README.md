# StageGuard

**Production-oriented Gemini/Google Cloud incident commander for live media workflows, with Grafana as the operational evidence plane.**

StageGuard is a personal open-source project. It investigates live-production failures through the official Grafana MCP server, correlates bounded Prometheus and Loki evidence, requires trusted human authorization for consequential remediation, verifies recovery from telemetry, preserves an incident audit trail, and can optionally use Gemini only for bounded operator communication above the deterministic safety core.

> Grafana gives the agent trustworthy operational evidence; StageGuard turns that evidence into bounded decisions and actions; Grafana then proves whether recovery actually happened.

## Current executable vertical slice

```text
deterministic broadcast simulator
  → Prometheus + Loki + Grafana
  → official grafana/mcp-grafana
  → strict semantic telemetry mapping
  → metric + Loki preflight
  → expiring datasource/contract activation pins
  → six-read metric diagnosis
  → mandatory production Loki corroboration
  → authenticated IncidentService
  → optional evidence-revision-bound Gemini briefing
  → authenticated same-origin operator cockpit
  → evidence-revision-bound human approval
  → disabled-by-default allowlisted remediation
  → credential-isolated HTTPS write transport
  → Grafana/Prometheus recovery verification
  → bounded local JSONL or Google Cloud Logging audit
  → Cloud Run/IAP deployment + liveness/readiness/self-observability
```

The deterministic fixture models three camera feeds and two uplinks. Its seeded incident is specific: `cam-3` drops frames because `uplink-b` has severe packet loss while encoder CPU/GPU and peer paths remain healthy.

## Safety model

| Boundary | Policy |
|---|---|
| Grafana MCP | Read-only evidence credentials; infrastructure-write credentials are separate |
| Metric onboarding | Strict versioned mapping; exactly eight bounded semantic metric checks must resolve |
| Loki onboarding | One StageGuard-owned causal LogQL contract is preflighted; callers never supply LogQL |
| Activation | Metric profile + Prometheus datasource and Loki contract + Loki datasource are independently SHA-256 pinned and time bounded |
| Investigation | Six policy-selected metric reads must independently diagnose before Loki is queried |
| Loki corroboration | Missing, truncated, scope-drifted, or inconsistent logs force abstention |
| Gemini commander | Advisory only; exact current incident revision required; cannot change diagnosis, approval, remediation, or recovery state |
| Identity | Actor identity comes from a trusted provider, never request JSON; production IAP uses the verified signed JWT `sub` claim |
| Operator cockpit | Same-origin, authenticated, no browser secrets/persistence, strict CSP, dynamic values rendered as text |
| Approval | Explicit, single-use approval is bound to the exact incident evidence revision |
| Remediation | Production writes are disabled by default; enabled writes are allowlisted, idempotent, timeout/retry bounded, and credential isolated |
| Recovery | Action acceptance never means recovery; Grafana telemetry must prove consecutive healthy samples |
| Audit | Bounded lifecycle records preserve trusted actor plus non-secret activation/action/briefing provenance |

## Production onboarding and activation

Real productions can map their existing Prometheus metric and label names in `runtime/telemetry.example.json`; datasource IDs and raw PromQL/LogQL are intentionally not accepted in that mapping.

With least-privilege Grafana MCP credentials configured:

```bash
python runtime/preflight.py runtime/telemetry.example.json \
  --activation-output .stageguard/activation.json \
  --log-activation-output .stageguard/log-activation.json
```

The metric preflight executes the same six investigation reads and two recovery reads used at runtime. The Loki preflight executes the exact bounded causal query StageGuard later uses. `runtime/activation.py` pins the full telemetry profile and actual Prometheus datasource UID; `runtime/log_activation.py` independently pins the Loki semantic contract and actual Loki datasource UID. Both activation records expire.

## Gemini boundary

`runtime/gemini_commander.py` sits above the deterministic evidence core. It does **not** receive remediation clients, credentials, endpoints, PromQL, LogQL, raw log bodies, arbitrary tools, or infrastructure write access.

`IncidentService.briefing()` binds generation to the exact current `incident_id + revision` while holding the lifecycle lock. A stale briefing request is rejected before the model is called. Successful generation does not alter incident, approval, remediation, or recovery state.

The optional `GoogleGenAICommanderModel` can be constructed for Vertex AI from `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, Application Default Credentials, and optional `STAGEGUARD_GEMINI_MODEL`. Gemini remains disabled by default.

## Operator cockpit

The first production operator surface is available at:

```text
GET /console
```

It is served by the same API process and protected by the same configured identity provider. In the Cloud Run deployment this means the existing verified IAP boundary remains authoritative; no separate frontend secret boundary is introduced.

The cockpit renders deterministic incident state, evidence revision, confidence, evidence slots, optional Gemini briefing, approval state, and recovery outcome. Approval requires the operator to type the exact current revision and then confirm explicitly. Server-side `IncidentService.approve()` remains authoritative regardless of browser state.

The browser assets use no third-party dependencies, no `localStorage`/`sessionStorage`, no Grafana/Gemini/remediation credentials, and a same-origin CSP. See `OPERATOR_CONSOLE.md`.

## Production identity and audit

`runtime/identity.py` includes `GoogleIapIdentityProvider`. StageGuard validates `X-Goog-IAP-JWT-Assertion` and uses the verified stable `sub` claim as operator identity. It deliberately ignores unsigned convenience identity headers for authentication.

`runtime/cloud_audit.py` adds `GoogleCloudLoggingAuditSink`, which writes bounded structured lifecycle events and rejects credential-, secret-, token-, endpoint-, prompt-, query-, raw-log-, oversized, binary, and deeply nested payloads.

See `GOOGLE_CLOUD_DEPLOYMENT.md` for the Cloud Run/IAP deployment contract.

## Governed remediation

Production bootstrap uses `DisabledRemediationClient` unless writes are explicitly enabled. `runtime/production_remediation.py` owns the allowlisted policy and `runtime/http_remediation_transport.py` owns the credential-isolated HTTPS transport.

The production action boundary supports one configured `recover_uplink` action/target, deterministic evidence-bound operation IDs, server-side idempotency keys, bounded timeout/retry behavior, strict response validation, and no inference that transport acceptance equals recovery.

The standard Cloud Run composition intentionally provides no environment flag that can enable production remediation.

## HTTP surfaces

Platform surfaces:

- `GET /healthz` — cheap process liveness only
- `GET /readyz` — bounded evidence-plane readiness with activation revalidation and cached external MCP checks
- `GET /metrics` — fixed non-sensitive Prometheus-format StageGuard readiness telemetry

Authenticated operator surfaces:

- `GET /console`
- `GET /assets/operator.css`
- `GET /assets/operator.js`
- `GET /v1/incident`
- `POST /v1/investigate`
- `POST /v1/briefing` — current `incident_id` + `revision`; advisory only
- `POST /v1/approve` — exact current `incident_id` + `revision`
- `POST /v1/execute` — consumes an existing server-side approval

Request bodies cannot supply actor identity, PromQL, LogQL, datasource IDs, prompts, remediation action names, targets, endpoints, or credentials.

## Local development

```bash
docker compose up --build -d
python runtime/bootstrap_grafana.py
python runtime/mcp_smoke.py
python runtime/preflight.py runtime/telemetry.example.json \
  --activation-output .stageguard/activation.json \
  --log-activation-output .stageguard/log-activation.json
```

Useful endpoints: simulator metrics `http://localhost:9108/metrics`, Prometheus `http://localhost:9090`, and Grafana `http://localhost:3000`.

## Repository structure

- `runtime/telemetry.py` — validated semantic metric mapping + query builders
- `runtime/onboarding.py` — strict profile loader + eight-slot metric preflight
- `runtime/activation.py` — metric profile/Prometheus datasource activation pin
- `runtime/log_evidence.py` — policy-owned Loki contract and corroboration rules
- `runtime/log_activation.py` — Loki preflight + contract/datasource activation pin
- `runtime/mcp_metric_client.py` — official Grafana MCP Prometheus adapter
- `runtime/mcp_log_client.py` — official Grafana MCP Loki adapter
- `runtime/investigator.py` — deterministic diagnosis + fail-closed Loki correlation
- `runtime/gemini_commander.py` — bounded Gemini advisory boundary
- `runtime/incident_service.py` — lifecycle, revision-bound briefing/approval, audit boundary
- `runtime/identity.py` — local, static bearer, and verified Google IAP identity providers
- `runtime/operator_console.py` — authenticated same-origin operator cockpit assets
- `runtime/readiness.py` — activation-aware MCP readiness cache/backoff + metrics
- `runtime/cloud_audit.py` — bounded Cloud Logging audit adapter
- `runtime/bootstrap.py` / `runtime/cloudrun_entrypoint.py` — production composition roots
- `runtime/production_remediation.py` — allowlisted write policy
- `runtime/http_remediation_transport.py` — credential-isolated HTTPS write transport
- `runtime/remediation.py` — approval and recovery verification
- `runtime/api.py` — authenticated API, cockpit, health/readiness/metrics surfaces
- `runtime/tests/` — credential-free regression coverage
- `OPERATOR_CONSOLE.md` — cockpit trust boundary and usage
- `GOOGLE_CLOUD_DEPLOYMENT.md` — IAP/Cloud Logging deployment boundary
- `ARCHITECTURE.md` — detailed architecture/trust boundaries
- `progress.md` — run-by-run implementation handoff

## Tests

```bash
PYTHONPATH=runtime python -m unittest discover -s runtime/tests -v
python -m py_compile runtime/*.py runtime/tests/*.py
```

The complete Docker → Grafana → official MCP path requires a Docker-capable host and valid local Grafana credentials. Missing Gemini, IAP, or Cloud Logging dependencies/credentials do not block the local deterministic core unless those modes are explicitly selected.

## Near-term roadmap

1. add a bounded, incident-scoped operator timeline over the audit boundary without exposing raw Cloud Logging access;
2. package and execute the Cloud Run + IAP + Cloud Logging path on a real Google Cloud project, including service-account least privilege and retention policy;
3. execute the full metric+Loki preflight/activation/investigation path against the pinned official MCP binary on a Docker-capable host and capture real tool/latency traces;
4. add a provider-controlled remediation deployment example preserving the existing allowlist/idempotency contract.

## Official references

- Grafana MCP introduction: https://grafana.com/docs/grafana/latest/developer-resources/mcp/introduction/
- Official Grafana MCP repository: https://github.com/grafana/mcp-grafana
- Google IAP identity: https://cloud.google.com/iap/docs/identity-howto
- Google IAP signed headers: https://cloud.google.com/iap/docs/signed-headers-howto
- IAP for Cloud Run: https://cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run
- Google Cloud Logging Python: https://cloud.google.com/logging/docs/write-query-log-entries-python
- Google Gen AI SDK structured output: https://ai.google.dev/gemini-api/docs/structured-output
- Vertex AI Google Gen AI SDK samples: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/samples

## Project status

StageGuard is under active development. Its production safety core now requires independently pinned Prometheus and Loki evidence planes, makes metric+Loki correlation canonical for non-demo startup, keeps Gemini briefings and human approval revision-bound, supports verified Google IAP operator identity, provides an authenticated same-origin operator cockpit, supports bounded centralized Cloud Logging audit, leaves production writes disabled by default, and verifies recovery from Grafana telemetry rather than action acknowledgement.
