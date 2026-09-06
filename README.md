# StageGuard

**Production-oriented Gemini/Google Cloud incident commander for live media workflows, with Grafana as the operational evidence plane.**

StageGuard is a personal open-source project. It investigates live-production failures through Grafana MCP, correlates bounded evidence, requires trusted human authorization for consequential remediation, verifies recovery from telemetry, and preserves an incident audit trail.

> **Grafana gives the agent trustworthy operational evidence; StageGuard turns that evidence into bounded decisions and actions; Grafana then proves whether recovery actually happened.**

## Current executable vertical slice

```text
deterministic broadcast simulator
  → Prometheus
  → Grafana
  → official grafana/mcp-grafana
  → strict telemetry-profile onboarding + eight-read preflight
  → hash-pinned, time-bounded activation record
  → production runtime/bootstrap
  → McpPrometheusMetricClient
  → bounded six-read investigator
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
| Onboarding | Versioned strict mapping; all semantic bindings explicit; exactly eight bounded checks must resolve before activation |
| Activation | Complete profile + datasource identity are SHA-256 pinned to a successful, time-bounded preflight; non-demo runtime refuses drift/staleness |
| Bootstrap | Runtime loads the exact profile + activation, derives datasource identity from the actual MCP client, and refuses unsafe network/auth combinations |
| Investigation | Fixed/bounded evidence contracts; missing evidence causes abstention |
| Identity | Operator identity comes from a configured authentication provider, never request JSON |
| Approval | Explicit approval bound to exact incident + evidence revision; approval is single-use |
| Remediation policy | Production policy pins one action and target, uses a deterministic evidence-bound operation ID, and bounds retries/timeouts |
| Remediation transport | Production network writes are disabled by default and require explicit startup opt-in, a fixed process-owned HTTPS endpoint, and a separate process-owned bearer credential |
| Recovery | Action success is never recovery; Grafana/Prometheus telemetry must prove health |
| Audit | Lifecycle events are appended with trusted actor identity, activation hashes, and non-secret remediation operation/result metadata when available |

The current investigator performs exactly six PromQL reads covering symptom, causal signal, contradiction evidence, and healthy-peer evidence. It emits `abstain` instead of allowing Gemini or another LLM to invent missing operational evidence.

## Production telemetry onboarding

Real productions do not need to rename their metrics or labels. Copy `runtime/telemetry.example.json`, then explicitly map every StageGuard semantic binding to the production's existing Prometheus schema. The loader rejects unknown fields, missing fields, unsupported versions, invalid identifier grammars, malformed peer lists, and configs larger than 64 KiB. It intentionally does **not** allow datasource IDs or arbitrary PromQL in the mapping file.

With least-privilege Grafana MCP credentials configured, run:

```bash
python runtime/preflight.py runtime/telemetry.example.json \
  --activation-output .stageguard/activation.json
```

Preflight executes exactly eight read-only semantic checks: the same six investigation slots plus the same two recovery slots used at runtime. A slot is `missing` if no sample exists and `error` if the metric adapter rejects the result, including ambiguous multi-series results. StageGuard reports `ready: true` only when all eight slots resolve to exactly one numeric observation.

When `--activation-output` is supplied and all eight checks pass, the CLI writes a versioned activation record that binds the validated `TelemetryProfile` and configured Grafana datasource UID by SHA-256. It expires after 24 hours by default; `--ttl-seconds` can shorten the window or extend it up to seven days. A failed or partial preflight never writes a usable activation record.

`IncidentService` treats the built-in deterministic fixture as an explicit local demo exception. Any non-default production mapping must present a matching, non-stale activation record plus the same datasource identity. Changing a metric, label, production/feed/uplink binding, peer set, datasource UID, or allowing activation to expire causes startup to fail closed and requires preflight to be rerun.

The activation artifact is a drift-prevention record, not a digital signature or substitute for host/file integrity controls.

## Production bootstrap

`runtime/bootstrap.py` is the canonical process entrypoint. It removes hand-written runtime glue by loading the strict telemetry mapping and activation artifact, constructing the official Grafana MCP metric adapter, deriving the datasource identity from that live adapter configuration, wiring append-only audit storage, choosing the operator identity provider, constructing `IncidentService`, and validating the final HTTP bind policy before serving.

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

`runtime/production_remediation.py` owns the policy half of the production write boundary. `runtime/http_remediation_transport.py` now supplies the first concrete deployment transport while preserving strict separation from Grafana evidence credentials.

`AllowlistedProductionRemediationClient` enforces:

- exactly one supported action: `recover_uplink`;
- one configured production ID and one configured uplink target;
- a deterministic operation ID derived from the exact diagnosed evidence + action + target;
- re-approval of identical evidence reuses the same operation ID;
- maximum timeout of 10 seconds per transport attempt;
- at most three attempts, with retries using the identical immutable request;
- no recovery inference from transport acceptance—Grafana telemetry still proves recovery;
- non-secret action metadata in the append-only lifecycle audit event.

`HttpRemediationTransport` adds these deployment constraints:

- HTTPS only; embedded credentials, URL query strings, and fragments are rejected;
- endpoint and bearer credential are process-owned configuration, never incident/API input;
- the write bearer credential is separate from `STAGEGUARD_API_TOKEN` and from Grafana MCP credentials;
- every POST sends the deterministic operation ID as both JSON data and `Idempotency-Key`;
- the remediation server must return exactly `{"accepted": <bool>, "operation_id": "<same-id>"}`;
- mismatched operation IDs, malformed JSON, unknown response fields, and oversized responses fail closed;
- only transient HTTP classes (`408`, `425`, `429`, selected `5xx`) are marked retryable;
- response bodies, endpoint URLs, and credentials are never copied into `TransportResult` or audit metadata.

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

## Authenticated incident API

`runtime/api.py` exposes only:

- `GET /healthz`
- `GET /v1/incident`
- `POST /v1/investigate`
- `POST /v1/approve`
- `POST /v1/execute`

No endpoint accepts PromQL, datasource identifiers, remediation action names, remediation targets, `actor`, or `approved_by`. The authenticated identity is resolved by `runtime/identity.py` and passed into the service/audit boundary.

Local development uses `LocalDevelopmentIdentityProvider`, safe only on loopback. `StaticBearerIdentityProvider` is a dependency-free deployment primitive for controlled deployments, normally behind TLS or an authenticated reverse proxy.

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

The MCP Compose profile is opt-in and constrained to read-only datasource/Prometheus capabilities. Secrets live under a gitignored local secrets directory and are not printed by the bootstrap path.

See [`runtime/README.md`](runtime/README.md) for the detailed local workflow and MCP contract.

## Repository structure

- `runtime/simulator.py` — deterministic media telemetry and controlled fault/recovery fixture
- `runtime/telemetry.py` — validated semantic telemetry mappings and bounded query builders
- `runtime/onboarding.py` — strict versioned mapping loader + eight-slot activation preflight
- `runtime/activation.py` — profile/datasource activation pinning, persistence, expiry, and runtime verification
- `runtime/preflight.py` — real Grafana/MCP readiness checks + activation artifact creation
- `runtime/bootstrap.py` — fail-closed production process wiring and API launcher
- `runtime/mcp_metric_client.py` — official Grafana MCP → metric client adapter
- `runtime/investigator.py` — bounded incident evidence policy
- `runtime/remediation.py` — approval-gated action dispatch, deterministic operation identity, and telemetry recovery verification
- `runtime/production_remediation.py` — allowlisted production write policy with injected deployment transport
- `runtime/http_remediation_transport.py` — strict credential-isolated HTTPS transport and server idempotency contract
- `runtime/incident_service.py` — activation-enforced lifecycle orchestration and append-only audit boundary
- `runtime/identity.py` — pluggable trusted operator identity providers
- `runtime/api.py` — narrow authenticated HTTP API
- `runtime/tests/` — deterministic policy/service/API/onboarding/activation/bootstrap/transport tests
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

1. execute the complete official-MCP onboarding/activation/bootstrap/diagnosis/approval/recovery path on a Docker-capable host and capture real latency/tool traces;
2. provide a tiny reference remediation receiver that demonstrates the server-side idempotency contract without real infrastructure mutation;
3. add Loki corroboration and evidence provenance across metrics + logs;
4. place Gemini above the deterministic safety core for incident summarization, bounded workflow selection, and operator communication;
5. build the authenticated operator incident console, OIDC/IAP identity, durable audit storage, and Google Cloud deployment path.

## Official references

- Grafana MCP introduction: https://grafana.com/docs/grafana/latest/developer-resources/mcp/introduction/
- Grafana MCP authentication: https://grafana.com/docs/grafana/latest/developer-resources/mcp/configure/authentication/
- Grafana MCP tool restriction: https://grafana.com/docs/grafana/latest/developer-resources/mcp/configure/enable-and-disable-tools/
- Official Grafana MCP repository: https://github.com/grafana/mcp-grafana
- Grafana MCP Observability: https://grafana.com/docs/grafana-cloud/observe-and-act/monitor-applications/ai-observability/mcp-observability/
- Gemini Enterprise Agent Platform Runtime quickstart: https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime/quickstart-adk

## Project status

StageGuard is under active development. The deterministic incident lifecycle now includes strict telemetry onboarding/preflight, hash-pinned activation, canonical fail-closed runtime bootstrap, bounded investigation, authenticated evidence-revision-bound approval, governed idempotent production-remediation policy, an explicit credential-isolated HTTPS write transport, telemetry-based recovery verification, and append-only audit logging. The major unproven integration gate remains executing that lifecycle through a live `grafana/mcp-grafana:1.1.0` process on a Docker-capable host.