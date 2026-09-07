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
  → eight-read Prometheus preflight
  → one bounded policy-owned Loki preflight
  → expiring metric activation + expiring Loki activation
  → canonical production bootstrap
  → six-read metric diagnosis
  → mandatory production Loki corroboration
  → authenticated IncidentService
  → optional evidence-revision-bound Gemini briefing
  → evidence-revision-bound human approval
  → disabled-by-default allowlisted remediation
  → credential-isolated HTTPS write transport
  → two-read Grafana/Prometheus recovery verification
  → bounded local JSONL or Google Cloud Logging audit
```

The deterministic fixture models three camera feeds and two uplinks. Its seeded incident is specific: `cam-3` drops frames because `uplink-b` has severe packet loss while encoder CPU/GPU and peer paths remain healthy.

## Safety model

StageGuard separates evidence, explanation, authorization, action, recovery, identity, and audit:

| Boundary | Policy |
|---|---|
| Grafana MCP | Read-only evidence credentials; infrastructure-write credentials are separate |
| Metric onboarding | Strict versioned mapping; exactly eight bounded semantic metric checks must resolve |
| Loki onboarding | Exactly one StageGuard-owned causal LogQL contract is preflighted; callers never supply LogQL |
| Activation | Metric profile + Prometheus datasource and Loki contract + Loki datasource are independently SHA-256 pinned and time bounded |
| Investigation | Six policy-selected metric reads must independently diagnose before Loki is queried |
| Loki corroboration | Missing, truncated, scope-drifted, or inconsistent logs force abstention |
| Gemini commander | Advisory only; exact current incident revision required; cannot change diagnosis, approval, remediation, or recovery state |
| Identity | Actor identity comes from a trusted provider, never request JSON; production IAP uses the verified signed JWT `sub` claim |
| Approval | Explicit, single-use approval is bound to the exact incident evidence revision |
| Remediation | Production writes are disabled by default; enabled writes are allowlisted, idempotent, timeout/retry bounded, and credential isolated |
| Recovery | Action acceptance never means recovery; Grafana telemetry must prove consecutive healthy samples |
| Audit | Bounded lifecycle records preserve trusted actor plus non-secret activation/action/briefing provenance |

## Production onboarding and activation

Real productions can map their existing Prometheus metric and label names in `runtime/telemetry.example.json`; datasource IDs and raw PromQL/LogQL are intentionally not accepted in that mapping.

With least-privilege Grafana MCP credentials configured, run both evidence preflights:

```bash
python runtime/preflight.py runtime/telemetry.example.json \
  --activation-output .stageguard/activation.json \
  --log-activation-output .stageguard/log-activation.json
```

The metric preflight executes the same six investigation reads and two recovery reads used at runtime and requires one unambiguous numeric sample per slot. The Loki preflight executes the exact bounded causal query StageGuard later uses. A healthy system may return zero matching log lines; the preflight proves the datasource/query contract rather than manufacturing an incident.

`runtime/activation.py` pins the full telemetry profile and actual Prometheus datasource UID. `runtime/log_activation.py` independently pins the exact Loki semantic contract and actual Loki datasource UID. Both records expire after 24 hours by default and may be configured up to seven days. Any non-demo production startup requires **both** records.

## Loki evidence contract

`runtime/log_evidence.py` generates one narrow causal query from trusted production/uplink scope. The current contract queries only the configured production/uplink, parses structured JSON, requires `event="packet_loss_alarm"`, uses a five-minute window, returns at most eight lines, rejects truncation and scope disagreement, and treats missing logs as missing corroboration rather than negative evidence.

`runtime/mcp_log_client.py` uses the official Grafana MCP `query_loki_logs` tool and verifies it advertises `readOnlyHint=true`. Loki cannot create a diagnosis or override contradictory metric evidence.

## Gemini incident-commander boundary

`runtime/gemini_commander.py` sits above the deterministic evidence core. It does **not** receive an `IncidentService`, remediation client, credentials, endpoints, PromQL, LogQL, raw log bodies, free-form report summaries, or infrastructure tools.

`IncidentService.briefing()` binds generation to the exact current `incident_id + revision` while holding the lifecycle lock. A stale briefing request is rejected before the model is called. Successful generation does not alter incident, approval, remediation, or recovery state. Audit records contain only the revision, deterministic next step, and SHA-256 digest of the returned briefing; model prose is not copied into lifecycle audit.

The optional `GoogleGenAICommanderModel` can be constructed for Vertex AI from `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, Application Default Credentials, and optional `STAGEGUARD_GEMINI_MODEL`. Gemini remains disabled by default.

## Production identity

`runtime/identity.py` now includes `GoogleIapIdentityProvider`. For production, configure the exact IAP Signed Header JWT audience and run with `--identity-mode iap`:

```bash
export STAGEGUARD_IAP_AUDIENCE='/projects/123456789/locations/us-central1/services/stageguard'

python runtime/bootstrap.py \
  --telemetry-config /etc/stageguard/telemetry.json \
  --activation /var/lib/stageguard/activation.json \
  --log-activation /var/lib/stageguard/log-activation.json \
  --host 0.0.0.0 \
  --identity-mode iap
```

StageGuard validates `X-Goog-IAP-JWT-Assertion` and uses the verified stable `sub` claim as operator identity. It deliberately ignores `X-Goog-Authenticated-User-Id` and `X-Goog-Authenticated-User-Email` for authentication because those unsigned headers are unsafe if IAP can be bypassed. The IAP path lazily requires `google-auth`; local development does not.

Static bearer auth is retained for explicit private/simple deployments and loopback development remains credential-free. Non-loopback local identity is refused.

See `GOOGLE_CLOUD_DEPLOYMENT.md` for the Cloud Run/IAP checklist.

## Durable audit

`runtime/cloud_audit.py` adds `GoogleCloudLoggingAuditSink`. It writes one structured `stageguard.audit.v1` entry per lifecycle event and enforces a small bounded schema before anything reaches Cloud Logging. Credential-, secret-, token-, endpoint-, prompt-, PromQL-, LogQL-, raw-log-, oversized, binary, and deeply nested payloads are rejected. Existing small remediation metadata is supported.

Production example:

```bash
pip install google-auth google-cloud-logging

python runtime/bootstrap.py \
  --telemetry-config /etc/stageguard/telemetry.json \
  --activation /var/lib/stageguard/activation.json \
  --log-activation /var/lib/stageguard/log-activation.json \
  --host 0.0.0.0 \
  --identity-mode iap \
  --audit-backend cloud-logging \
  --cloud-log-name stageguard-audit
```

The Cloud Logging client uses Application Default Credentials from the runtime service account. StageGuard does not claim Cloud Logging itself is immutable; deployments that require stronger retention should route the dedicated log to an organization-approved retained/locked destination.

## Governed production remediation

Production bootstrap uses `DisabledRemediationClient` unless writes are explicitly enabled. `runtime/production_remediation.py` owns the allowlisted policy and `runtime/http_remediation_transport.py` owns the credential-isolated HTTPS transport.

The production action boundary supports one configured `recover_uplink` action/target, deterministic evidence-bound operation IDs, server-side idempotency keys, bounded timeout/retry behavior, strict response validation, and no inference that transport acceptance equals recovery.

```bash
export STAGEGUARD_REMEDIATION_ENDPOINT='https://remediation.example.com/v1/recover'
export STAGEGUARD_REMEDIATION_TOKEN='separate-write-secret'

python runtime/bootstrap.py \
  --telemetry-config /etc/stageguard/telemetry.json \
  --activation /var/lib/stageguard/activation.json \
  --log-activation /var/lib/stageguard/log-activation.json \
  --host 0.0.0.0 \
  --identity-mode iap \
  --audit-backend cloud-logging \
  --enable-production-remediation
```

The demo profile explicitly refuses the production-write opt-in. `runtime/remediation_receiver.py` is a loopback-only reference server for testing exact-retry idempotency without touching infrastructure.

## Incident API

`runtime/api.py` exposes only:

- `GET /healthz`
- `GET /v1/incident`
- `POST /v1/investigate`
- `POST /v1/briefing` — current `incident_id` + `revision`; advisory only
- `POST /v1/approve`
- `POST /v1/execute`

All non-health endpoints are authenticated. Request bodies cannot supply actor identity, PromQL, LogQL, datasource IDs, prompts, remediation action names, targets, endpoints, or credentials.

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

The deterministic demo can run without activation artifacts as an explicit local-only exception.

## Repository structure

- `runtime/telemetry.py` — validated semantic metric mapping + query builders
- `runtime/onboarding.py` — strict profile loader + eight-slot metric preflight
- `runtime/activation.py` — metric profile/Prometheus datasource activation pin
- `runtime/log_evidence.py` — policy-owned semantic Loki contract and corroboration rules
- `runtime/log_activation.py` — bounded Loki preflight + contract/datasource activation pin
- `runtime/mcp_metric_client.py` — official Grafana MCP Prometheus adapter
- `runtime/mcp_log_client.py` — official Grafana MCP Loki adapter
- `runtime/investigator.py` — deterministic metric diagnosis + fail-closed Loki correlation
- `runtime/gemini_commander.py` — bounded Gemini advisory boundary
- `runtime/incident_service.py` — activation-aware lifecycle, revision-bound briefing, audit boundary
- `runtime/identity.py` — local, static bearer, and verified Google IAP identity providers
- `runtime/cloud_audit.py` — bounded Cloud Logging audit adapter
- `runtime/bootstrap.py` — canonical production composition/root of trust
- `runtime/production_remediation.py` — allowlisted write policy
- `runtime/http_remediation_transport.py` — credential-isolated HTTPS write transport
- `runtime/remediation.py` — approval and recovery verification
- `runtime/api.py` — narrow authenticated operator API
- `runtime/tests/` — credential-free regression coverage
- `GOOGLE_CLOUD_DEPLOYMENT.md` — IAP/Cloud Logging deployment boundary
- `ARCHITECTURE.md` — detailed architecture/trust boundaries
- `progress.md` — exact run-by-run implementation handoff

## Tests

```bash
PYTHONPATH=runtime python -m unittest discover -s runtime/tests -v
python -m py_compile runtime/*.py runtime/tests/*.py
```

The complete Docker → Grafana → official MCP path requires a Docker-capable host and valid local Grafana credentials. Missing Gemini, IAP, or Cloud Logging dependencies/credentials do not block the local deterministic core unless their modes are explicitly selected.

## Near-term roadmap

1. package and execute the Cloud Run + IAP + Cloud Logging deployment path on a real Google Cloud project, including retention policy and service-account least privilege;
2. execute the full metric+Loki preflight/activation/investigation path against the pinned official MCP image on a Docker-capable host and capture real tool/latency traces;
3. add an operator console that renders deterministic evidence and revision-bound Gemini briefing side-by-side without introducing browser-side write secrets;
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

StageGuard is under active development. Its production safety core now requires independently pinned Prometheus and Loki evidence planes, makes metric+Loki correlation canonical for non-demo startup, keeps Gemini briefings and human approval revision-bound, supports verified Google IAP operator identity, supports bounded centralized Cloud Logging audit, leaves production writes disabled by default, and verifies recovery from Grafana telemetry rather than action acknowledgement.
