# StageGuard

**Production-oriented Gemini/Google Cloud incident commander for live media workflows, with Grafana as the operational evidence plane.**

StageGuard is a personal open-source project. It investigates live-production failures through Grafana MCP, correlates bounded evidence, requires trusted human authorization for consequential remediation, verifies recovery from telemetry, and preserves an incident audit trail.

> **Grafana gives the agent trustworthy operational evidence; StageGuard turns that evidence into bounded decisions and actions; Grafana then proves whether recovery actually happened.**

## Current executable vertical slice

```text
deterministic broadcast simulator
  → Prometheus / Grafana
  → official grafana/mcp-grafana
  → strict metric-profile onboarding + eight-read preflight
  → hash-pinned, time-bounded activation record
  → production runtime/bootstrap
  → McpPrometheusMetricClient
  → bounded six-read metric investigator
  → optional McpLokiLogClient bounded corroboration
  → activation-enforced IncidentService
  → authenticated operator identity
  → evidence-revision-bound human approval
  → governed allowlisted remediation policy
  → explicit credential-isolated HTTPS remediation transport
  → bounded two-read telemetry recovery verification
  → append-only audit record
```

The local fixture models three camera feeds and two uplinks. The seeded incident is deliberately specific: `cam-3` drops frames because `uplink-b` has severe packet loss while encoder CPU/GPU and peer feeds remain healthy.

## Safety model

StageGuard keeps observation, authorization, and action structurally separate.

| Boundary | Policy |
|---|---|
| Grafana / MCP | Read-only evidence plane with least-privilege credentials |
| Onboarding | Versioned strict metric mapping; all semantic bindings explicit; exactly eight bounded metric checks must resolve before activation |
| Activation | Complete metric profile + Prometheus datasource identity are SHA-256 pinned to a successful, time-bounded preflight; non-demo runtime refuses drift/staleness |
| Investigation | Fixed/bounded evidence contracts; missing evidence causes abstention |
| Loki corroboration | One policy-owned LogQL query may corroborate an already-supported metric diagnosis; missing, truncated, scope-drifted, or event-drifted log evidence causes abstention |
| Identity | Operator identity comes from a configured authentication provider, never request JSON |
| Approval | Explicit approval bound to exact incident + evidence revision; approval is single-use |
| Remediation policy | Production policy pins one action and target, uses a deterministic evidence-bound operation ID, and bounds retries/timeouts |
| Remediation transport | Production network writes are disabled by default and require explicit startup opt-in, a fixed process-owned HTTPS endpoint, and a separate process-owned bearer credential |
| Recovery | Action success is never recovery; Grafana/Prometheus telemetry must prove health |
| Audit | Lifecycle events are appended with trusted actor identity, activation hashes, and non-secret remediation operation/result metadata when available |

The base investigator performs exactly six PromQL reads covering symptom, causal signal, contradiction evidence, and healthy-peer evidence. The stricter correlated mode adds one bounded Loki read only after those metrics already support the diagnosis. Loki cannot create a diagnosis or override contradictory metrics.

## Metric onboarding and activation

Real productions do not need to rename their metrics or labels. Copy `runtime/telemetry.example.json`, then explicitly map every StageGuard semantic binding to the production's existing Prometheus schema. The loader rejects unknown fields, missing fields, unsupported versions, invalid identifier grammars, malformed peer lists, and configs larger than 64 KiB. It intentionally does **not** allow datasource IDs or arbitrary PromQL in the mapping file.

With least-privilege Grafana MCP credentials configured, run:

```bash
python runtime/preflight.py runtime/telemetry.example.json \
  --activation-output .stageguard/activation.json
```

Preflight executes exactly eight read-only semantic metric checks: the same six investigation slots plus the same two recovery slots used at runtime. A slot is `missing` if no sample exists and `error` if the metric adapter rejects the result, including ambiguous multi-series results. StageGuard reports `ready: true` only when all eight slots resolve to exactly one numeric observation.

When `--activation-output` is supplied and all eight checks pass, the CLI writes a versioned activation record that binds the validated `TelemetryProfile` and configured Grafana Prometheus datasource UID by SHA-256. It expires after 24 hours by default; `--ttl-seconds` can shorten the window or extend it up to seven days. A failed or partial preflight never writes a usable activation record.

`IncidentService` treats the built-in deterministic fixture as an explicit local demo exception. Any non-default production mapping must present a matching, non-stale activation record plus the same datasource identity. Changing a metric, label, production/feed/uplink binding, peer set, datasource UID, or allowing activation to expire causes startup to fail closed and requires preflight to be rerun.

The activation artifact is a drift-prevention record, not a digital signature or substitute for host/file integrity controls.

## Loki corroboration

`runtime/log_evidence.py` and `runtime/mcp_log_client.py` implement a second, read-only evidence plane using the official Grafana MCP `query_loki_logs` tool.

The current causal log contract is intentionally narrow:

- LogQL is generated by StageGuard from trusted production/uplink bindings; incident API callers cannot submit arbitrary LogQL.
- The query is bounded to a five-minute window and at most eight returned lines.
- The stream must match the configured production and affected uplink.
- A structured `event="packet_loss_alarm"` identity is required; free-text keyword matching is not sufficient.
- Official MCP result metadata is checked for truncation. Older metadata-less responses that exactly fill the requested limit are conservatively treated as potentially truncated.
- Missing logs are treated as missing corroboration, not proof that the metric diagnosis is false.
- Truncated or internally inconsistent results are `ambiguous` and fail closed.

`investigate_with_log_corroboration()` first executes the normal six metric reads. Only if they return `diagnosed` does it perform the single Loki read. Successful Loki evidence is attached to the incident report and therefore participates in the evidence revision.

**Production note:** the canonical bootstrap is not yet switched to mandatory Loki corroboration because the existing activation artifact pins only the metric profile and Prometheus datasource. The next production gate is to include the Loki datasource identity and semantic log contract in onboarding/activation before enforcing correlated mode at startup.

## Production bootstrap

`runtime/bootstrap.py` is the canonical process entrypoint. It loads the strict metric mapping and activation artifact, constructs the official Grafana MCP metric adapter, derives datasource identity from that live adapter configuration, wires append-only audit storage, chooses the operator identity provider, constructs `IncidentService`, and validates the final HTTP bind policy before serving.

Loopback development can use the fixed local identity. A non-loopback bind requires a process-owned bearer credential:

```bash
export STAGEGUARD_API_TOKEN='replace-with-secret'
export STAGEGUARD_API_SUBJECT='operator@example.com'
python runtime/bootstrap.py \
  --telemetry-config runtime/telemetry.example.json \
  --activation .stageguard/activation.json \
  --audit-log .stageguard/audit.jsonl \
  --host 0.0.0.0 \
  --port 9110
```

For real production profiles, `--activation` is mandatory and is verified against the datasource UID of the actual `McpPrometheusMetricClient`. If either the mapping or datasource differs from preflight, startup is refused before incident handling begins. Tokens are read from environment variables and are not accepted through request bodies or written to audit records.

Production bootstrap uses a `DisabledRemediationClient` unless writes are explicitly enabled. The local deterministic demo remains wired to the loopback-only simulator remediation adapter.

## Governed production remediation

`runtime/production_remediation.py` owns the policy half of the production write boundary. `runtime/http_remediation_transport.py` supplies the first concrete deployment transport while preserving strict separation from Grafana evidence credentials.

`AllowlistedProductionRemediationClient` enforces exactly one supported action (`recover_uplink`), one configured production/uplink target, deterministic evidence-bound operation IDs, bounded timeouts/retries, and no recovery inference from transport acceptance.

`HttpRemediationTransport` adds HTTPS-only process-owned endpoint configuration, a bearer credential separate from both operator/API and Grafana credentials, server-side `Idempotency-Key`, strict response validation, bounded response size, transient-only retry classification, and redaction of response bodies/endpoints/credentials from result metadata.

Production writes require an explicit startup flag plus deployment-owned environment settings:

```bash
export STAGEGUARD_API_TOKEN='operator-api-secret'
export STAGEGUARD_API_SUBJECT='operator@example.com'
export STAGEGUARD_REMEDIATION_ENDPOINT='https://remediation.example.com/v1/recover'
export STAGEGUARD_REMEDIATION_TOKEN='separate-write-secret'

python runtime/bootstrap.py \
  --telemetry-config /etc/stageguard/telemetry.json \
  --activation /var/lib/stageguard/activation.json \
  --audit-log /var/lib/stageguard/audit.jsonl \
  --host 0.0.0.0 \
  --port 9110 \
  --enable-production-remediation
```

Without `--enable-production-remediation`, production writes remain disabled even when remediation environment variables are present. The demo profile explicitly refuses the production-write opt-in.

For credential-free contract testing, `runtime/remediation_receiver.py` provides a loopback-only reference receiver. It validates bearer authentication, request schema, and `Idempotency-Key`; accepts exact retries idempotently; rejects reuse of an operation ID for a different mutation; and never touches real infrastructure.

## Authenticated incident API

`runtime/api.py` exposes only:

- `GET /healthz`
- `GET /v1/incident`
- `POST /v1/investigate`
- `POST /v1/approve`
- `POST /v1/execute`

No endpoint accepts PromQL, LogQL, datasource identifiers, remediation action names, remediation targets, `actor`, or `approved_by`. The authenticated identity is resolved by `runtime/identity.py` and passed into the service/audit boundary.

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

Then prove a real official-MCP metric read and create an activation artifact:

```bash
python runtime/mcp_smoke.py
python runtime/preflight.py runtime/telemetry.example.json \
  --activation-output .stageguard/activation.json
```

The MCP Compose profile is opt-in and constrained to read-only query capabilities. Secrets live under a gitignored local secrets directory and are not printed by the bootstrap path.

See [`runtime/README.md`](runtime/README.md) for the detailed local workflow and MCP contract.

## Repository structure

- `runtime/simulator.py` — deterministic media telemetry and controlled fault/recovery fixture
- `runtime/telemetry.py` — validated semantic metric mappings and bounded query builders
- `runtime/onboarding.py` — strict versioned mapping loader + eight-slot metric activation preflight
- `runtime/activation.py` — metric profile/datasource activation pinning, persistence, expiry, and runtime verification
- `runtime/preflight.py` — real Grafana/MCP metric readiness checks + activation artifact creation
- `runtime/bootstrap.py` — fail-closed production process wiring and API launcher
- `runtime/mcp_metric_client.py` — official Grafana MCP → Prometheus metric adapter
- `runtime/mcp_log_client.py` — official Grafana MCP → bounded Loki log adapter
- `runtime/log_evidence.py` — policy-owned semantic LogQL and corroboration rules
- `runtime/investigator.py` — six-read metric policy plus optional fail-closed Loki-correlated mode
- `runtime/remediation.py` — approval-gated action dispatch and telemetry recovery verification
- `runtime/production_remediation.py` — allowlisted production write policy with injected deployment transport
- `runtime/http_remediation_transport.py` — strict credential-isolated HTTPS transport and server idempotency contract
- `runtime/remediation_receiver.py` — loopback-only reference receiver for server-side idempotency testing
- `runtime/incident_service.py` — activation-enforced lifecycle orchestration and append-only audit boundary
- `runtime/identity.py` — pluggable trusted operator identity providers
- `runtime/api.py` — narrow authenticated HTTP API
- `runtime/tests/` — deterministic policy/service/API/onboarding/activation/bootstrap/transport/log tests
- `runtime/grafana/`, `runtime/prometheus/` — local observability provisioning
- `ARCHITECTURE.md` — architecture and trust-boundary detail
- `progress.md` — exact implementation/run log and next step

## Tests

The deterministic Python tests intentionally avoid paid services and API keys:

```bash
python -m unittest discover -s runtime/tests -v
python -m py_compile runtime/*.py runtime/tests/*.py
```

The Docker → Grafana → official MCP gate still requires a Docker-capable host. Missing cloud/Gemini credentials do not block local implementation or safety testing.

## Near-term roadmap

1. pin Loki datasource + semantic log contract in onboarding/activation and make correlated investigation the canonical production path;
2. execute the complete official-MCP onboarding/activation/metric+log diagnosis/approval/recovery path on a Docker-capable host and capture real latency/tool traces;
3. place Gemini above the deterministic safety core for incident summarization, bounded workflow selection, and operator communication;
4. build the authenticated operator incident console, OIDC/IAP identity, durable audit storage, and Google Cloud deployment path;
5. add a deployment example that replaces the reference receiver with a real provider-controlled remediation endpoint while preserving the same idempotency contract.

## Official references

- Grafana MCP introduction: https://grafana.com/docs/grafana/latest/developer-resources/mcp/introduction/
- Grafana MCP authentication: https://grafana.com/docs/grafana/latest/developer-resources/mcp/configure/authentication/
- Grafana MCP tool restriction: https://grafana.com/docs/grafana/latest/developer-resources/mcp/configure/enable-and-disable-tools/
- Official Grafana MCP repository: https://github.com/grafana/mcp-grafana
- Official Loki tool implementation: https://github.com/grafana/mcp-grafana/blob/main/tools/loki.go
- Grafana MCP Observability: https://grafana.com/docs/grafana-cloud/observe-and-act/monitor-applications/ai-observability/mcp-observability/
- Gemini Enterprise Agent Platform Runtime quickstart: https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime/quickstart-adk

## Project status

StageGuard is under active development. The deterministic lifecycle now includes strict metric onboarding/preflight, hash-pinned activation, canonical fail-closed runtime bootstrap, bounded metric diagnosis, a bounded official-MCP Loki corroboration layer, authenticated evidence-revision-bound approval, governed idempotent production remediation, telemetry-based recovery verification, and append-only audit logging. Loki correlation is implemented but intentionally not yet mandatory in canonical production bootstrap until Loki identity/policy are activation-pinned.
