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
  → bounded Gemini operator-briefing boundary (optional)
  → authenticated IncidentService
  → evidence-revision-bound human approval
  → disabled-by-default allowlisted remediation
  → credential-isolated HTTPS write transport
  → two-read Grafana/Prometheus recovery verification
  → append-only audit trail
```

The deterministic fixture models three camera feeds and two uplinks. Its seeded incident is specific: `cam-3` drops frames because `uplink-b` has severe packet loss while encoder CPU/GPU and peer paths remain healthy.

## Safety model

StageGuard separates evidence, explanation, authorization, action, and recovery:

| Boundary | Policy |
|---|---|
| Grafana MCP | Read-only evidence credentials; infrastructure-write credentials are separate |
| Metric onboarding | Strict versioned mapping; exactly eight bounded semantic metric checks must resolve |
| Loki onboarding | Exactly one StageGuard-owned causal LogQL contract is preflighted; callers never supply LogQL |
| Activation | Metric profile + Prometheus datasource and Loki contract + Loki datasource are independently SHA-256 pinned and time bounded |
| Investigation | Six policy-selected metric reads must independently diagnose before Loki is queried |
| Loki corroboration | Missing, truncated, scope-drifted, or inconsistent logs force abstention |
| Gemini commander | Advisory only: receives a bounded structured projection, no raw queries/log bodies/write secrets, and cannot change diagnosis, approval, remediation, or recovery state |
| Identity | Actor identity comes from the configured identity provider, never request JSON |
| Approval | Explicit, single-use approval is bound to the exact incident evidence revision |
| Remediation | Production writes are disabled by default; enabled writes are allowlisted, idempotent, timeout/retry bounded, and credential isolated |
| Recovery | Action acceptance never means recovery; Grafana telemetry must prove consecutive healthy samples |
| Audit | Lifecycle events preserve trusted actor and non-secret activation/action provenance |

## Production onboarding and activation

Real productions can map their existing Prometheus metric and label names in `runtime/telemetry.example.json`; datasource IDs and raw PromQL/LogQL are intentionally not accepted in that mapping.

With least-privilege Grafana MCP credentials configured, run both evidence preflights and write both activation records:

```bash
python runtime/preflight.py runtime/telemetry.example.json \
  --activation-output .stageguard/activation.json \
  --log-activation-output .stageguard/log-activation.json
```

The metric preflight executes the same six investigation reads and two recovery reads used at runtime and requires one unambiguous numeric sample per slot. The Loki preflight executes the exact bounded causal query StageGuard will later use. A healthy system may legitimately return zero matching log lines; the purpose of this preflight is to prove the datasource/query contract and reject truncation or scope drift, not to manufacture an incident.

`runtime/activation.py` pins the full telemetry profile and actual Prometheus datasource UID. `runtime/log_activation.py` independently pins the exact Loki semantic contract and actual Loki datasource UID. Both records expire after 24 hours by default and may be configured up to seven days. They are drift-prevention records, not digital signatures or substitutes for host/file integrity controls.

Any non-demo production startup now requires **both** records. Changing the metric mapping, production/feed/uplink scope, peer set, Prometheus datasource, Loki datasource, or Loki evidence contract causes startup to fail closed until preflight is rerun.

## Loki evidence contract

`runtime/log_evidence.py` generates one narrow causal query from trusted production/uplink scope. The current contract:

- queries only the configured production and affected uplink;
- parses structured JSON;
- requires `event="packet_loss_alarm"`;
- uses a five-minute window;
- returns at most eight lines;
- rejects truncated results;
- rejects production/uplink scope disagreement;
- treats missing logs as missing corroboration rather than negative evidence.

`runtime/mcp_log_client.py` uses the official Grafana MCP `query_loki_logs` tool and verifies it advertises `readOnlyHint=true`. Loki cannot create a diagnosis or override contradictory metric evidence.

## Gemini incident-commander boundary

`runtime/gemini_commander.py` is the first Gemini/Google Cloud layer above the deterministic evidence core. It intentionally does **not** receive an `IncidentService`, remediation client, credentials, endpoints, PromQL, LogQL, raw log bodies, free-form report summaries, or infrastructure tools.

Instead, `build_commander_context()` projects an already-computed `IncidentReport` into a small schema containing trusted identifiers, deterministic status/confidence, at most six numeric metric evidence slots, bounded missing-evidence classes, Loki corroboration status, and a deterministic next-step policy. The model can produce only five operator-facing fields. Validation rejects extra fields, oversized text, unsafe identifiers, and any attempt to change the deterministic next step:

- `diagnosed` → `seek_human_approval`
- `abstain` → `collect_more_evidence`
- `no_incident` → `observe`

The optional `GoogleGenAICommanderModel` uses the current Google Gen AI SDK structured-output path and can be constructed for Vertex AI from `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, and Application Default Credentials. `google-genai` is intentionally an optional dependency so the safety core and deterministic tests remain credential-free.

This separation is deliberate: Gemini may explain evidence to an operator, but it cannot manufacture a diagnosis, grant approval, invoke remediation, or declare recovery.

## Production bootstrap

`runtime/bootstrap.py` is the canonical process entrypoint. For a real production profile it constructs both live MCP clients, verifies each activation against the datasource UID of the actual client, and injects the verified Loki client into `IncidentService`. Production investigations therefore use metric+Loki correlation by default; the metric-only path remains available for the deterministic local demo and direct unit-level use.

Example:

```bash
export STAGEGUARD_API_TOKEN='replace-with-secret'
export STAGEGUARD_API_SUBJECT='operator@example.com'

python runtime/bootstrap.py \
  --telemetry-config /etc/stageguard/telemetry.json \
  --activation /var/lib/stageguard/activation.json \
  --log-activation /var/lib/stageguard/log-activation.json \
  --audit-log /var/lib/stageguard/audit.jsonl \
  --host 0.0.0.0 \
  --port 9110
```

A non-loopback bind requires a process-owned bearer token. Request bodies cannot supply PromQL, LogQL, datasource IDs, actor identity, remediation action names, remediation targets, endpoints, or credentials.

## Governed production remediation

Production bootstrap uses `DisabledRemediationClient` unless writes are explicitly enabled. `runtime/production_remediation.py` owns the allowlisted policy and `runtime/http_remediation_transport.py` owns the credential-isolated HTTPS transport.

The current production action boundary supports one configured `recover_uplink` action/target, deterministic evidence-bound operation IDs, server-side idempotency keys, bounded timeout/retry behavior, strict response validation, and no inference that transport acceptance equals recovery.

To opt in:

```bash
export STAGEGUARD_REMEDIATION_ENDPOINT='https://remediation.example.com/v1/recover'
export STAGEGUARD_REMEDIATION_TOKEN='separate-write-secret'

python runtime/bootstrap.py \
  --telemetry-config /etc/stageguard/telemetry.json \
  --activation /var/lib/stageguard/activation.json \
  --log-activation /var/lib/stageguard/log-activation.json \
  --host 0.0.0.0 \
  --enable-production-remediation
```

The demo profile explicitly refuses the production-write opt-in. `runtime/remediation_receiver.py` is a loopback-only credential-free reference server for testing exact-retry idempotency without touching infrastructure.

## Incident API

`runtime/api.py` exposes only:

- `GET /healthz`
- `GET /v1/incident`
- `POST /v1/investigate`
- `POST /v1/approve`
- `POST /v1/execute`

Successful production investigation audit events include non-secret hashes for the metric activation and Loki activation/contract. Raw production log lines are evidence in the incident report, not copied wholesale into lifecycle audit metadata.

## Local development

Start the simulator, Prometheus, and Grafana:

```bash
docker compose up --build -d
```

Useful endpoints:

- simulator metrics: `http://localhost:9108/metrics`
- simulator state: `http://localhost:9108/state`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

Bootstrap a least-privilege local Grafana MCP credential:

```bash
python runtime/bootstrap_grafana.py
```

Then run the official-MCP smoke/preflight path:

```bash
python runtime/mcp_smoke.py
python runtime/preflight.py runtime/telemetry.example.json \
  --activation-output .stageguard/activation.json \
  --log-activation-output .stageguard/log-activation.json
```

The deterministic demo can still run without activation artifacts as an explicit local-only exception.

## Repository structure

- `runtime/telemetry.py` — validated semantic metric mapping + query builders
- `runtime/onboarding.py` — strict profile loader + eight-slot metric preflight
- `runtime/activation.py` — metric profile/Prometheus datasource activation pin
- `runtime/log_evidence.py` — policy-owned semantic Loki contract and corroboration rules
- `runtime/log_activation.py` — bounded Loki preflight + contract/datasource activation pin
- `runtime/mcp_metric_client.py` — official Grafana MCP Prometheus adapter
- `runtime/mcp_log_client.py` — official Grafana MCP Loki adapter
- `runtime/investigator.py` — deterministic metric diagnosis + fail-closed Loki correlation
- `runtime/gemini_commander.py` — bounded Gemini advisory/structured operator-briefing boundary
- `runtime/incident_service.py` — activation-aware lifecycle and append-only audit boundary
- `runtime/bootstrap.py` — canonical production composition/root of trust
- `runtime/production_remediation.py` — allowlisted write policy
- `runtime/http_remediation_transport.py` — credential-isolated HTTPS write transport
- `runtime/remediation.py` — approval and recovery verification
- `runtime/api.py`, `runtime/identity.py` — authenticated narrow operator API
- `runtime/tests/` — credential-free regression coverage
- `ARCHITECTURE.md` — detailed architecture/trust boundaries
- `progress.md` — exact run-by-run implementation handoff

## Tests

```bash
python -m unittest discover -s runtime/tests -v
python -m py_compile runtime/*.py runtime/tests/*.py
```

The complete Docker → Grafana → official MCP path requires a Docker-capable host and valid local Grafana credentials. Missing Gemini/Google Cloud credentials do not block the deterministic safety core or the injected commander-model fixture tests.

## Near-term roadmap

1. wire the bounded Gemini commander into the authenticated incident API/runtime as an optional advisory endpoint, preserving the no-write/no-state-mutation boundary;
2. execute the full metric+Loki preflight/activation/investigation path against the pinned official MCP image on a Docker-capable host and capture real tool/latency traces;
3. add OIDC/IAP identity, tamper-resistant durable audit storage, operator console, and Google Cloud deployment;
4. add a real provider-controlled remediation deployment example preserving the same allowlist/idempotency contract.

## Official references

- Grafana MCP introduction: https://grafana.com/docs/grafana/latest/developer-resources/mcp/introduction/
- Grafana MCP authentication: https://grafana.com/docs/grafana/latest/developer-resources/mcp/configure/authentication/
- Grafana MCP tool restriction: https://grafana.com/docs/grafana/latest/developer-resources/mcp/configure/enable-and-disable-tools/
- Official Grafana MCP repository: https://github.com/grafana/mcp-grafana
- Official Loki tool implementation: https://github.com/grafana/mcp-grafana/blob/main/tools/loki.go
- Google Gen AI SDK / structured output: https://ai.google.dev/gemini-api/docs/structured-output
- Vertex AI Google Gen AI SDK samples: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/samples
- Gemini Enterprise Agent Platform Runtime quickstart: https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime/quickstart-adk

## Project status

StageGuard is under active development. The production safety core requires independently pinned Prometheus and Loki evidence planes, makes metric+Loki correlation canonical for non-demo production startup, keeps human approval revision-bound, leaves production writes disabled by default, verifies recovery from Grafana telemetry rather than action acknowledgement, and now has a bounded Gemini advisory layer that cannot alter deterministic incident authority.