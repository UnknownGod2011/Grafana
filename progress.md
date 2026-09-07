# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable production safety core now covers:

`strict telemetry mapping → eight-read metric preflight → metric activation pin → one bounded Loki preflight → Loki contract/datasource activation pin → official Grafana MCP Prometheus + Loki adapters → six-read metric diagnosis → mandatory production Loki corroboration → audited IncidentService → trusted operator identity → revision-bound approval → governed allowlisted remediation → explicit credential-isolated HTTPS transport → two-read telemetry recovery verification`

Core invariants:

- Grafana remains the evidence plane; infrastructure write credentials remain separate.
- Callers never provide raw PromQL, raw LogQL, datasource IDs, remediation actions, targets, endpoints, or credentials through the incident API.
- Production metric mappings are explicit and validated; omitted values never inherit demo scope.
- Metric preflight performs exactly six investigation reads plus two recovery reads and requires exactly one numeric sample per slot.
- Metric activation binds the complete semantic profile and the actual Prometheus datasource identity by SHA-256 and expiry.
- Loki preflight executes exactly one StageGuard-owned bounded causal query. An empty healthy window is valid; truncation or returned scope drift is not.
- Loki activation independently binds the exact semantic log contract and actual Loki datasource identity by SHA-256 and expiry.
- Canonical non-demo production startup requires both activation records and verifies both against the datasource identities of the actual MCP client instances.
- Production investigation now uses six metric reads first and queries Loki only if metrics independently diagnose the configured uplink-loss hypothesis.
- Missing Loki corroboration causes abstention; truncated or inconsistent Loki evidence is ambiguous and also causes abstention.
- Approval is tied to the exact evidence revision, single-use, and invalidated by fresh investigation.
- Production writes require explicit startup opt-in plus separate process-owned endpoint/credential configuration.
- Action acceptance is never recovery; Grafana telemetry must prove consecutive healthy samples.

## Completed milestones

- Deterministic broadcast telemetry simulator + Prometheus + provisioned Grafana local stack.
- Opt-in pinned official `grafana/mcp-grafana:1.1.0` path with write tools disabled.
- Deterministic four-class incident investigation with exactly six metric reads.
- MCP Prometheus metric adapter with fail-closed scalar/vector parsing and query provenance.
- Approval-gated remediation with a distinct write boundary and telemetry-only recovery proof.
- Audited incident lifecycle service and narrow authenticated HTTP API.
- Loopback development identity plus explicit static-bearer deployment primitive.
- Strict configurable production telemetry mapping and eight-slot readiness preflight.
- SHA-256 pinned, expiring metric activation artifact for non-demo profiles.
- Canonical production bootstrap wiring mapping + metric activation + MCP metric datasource + audit + auth + service + bind policy.
- Governed production remediation policy with deterministic operation identity, bounded retry/timeout semantics, and non-secret audit metadata.
- Concrete HTTPS remediation transport with separate write credential and server idempotency contract.
- Loopback-only reference remediation receiver proving exact-retry idempotency without real infrastructure mutation.
- Bounded semantic Loki corroboration contract generated from trusted telemetry scope rather than caller LogQL.
- Official Grafana MCP `query_loki_logs` adapter with read-only-tool verification, strict response parsing, bounds, traces, and conservative truncation detection.
- Correlated investigator mode in which Loki may only corroborate an already-supported metric diagnosis and missing/ambiguous logs fail closed.
- Separate Loki activation record pinning the exact log contract + actual Loki datasource identity.
- Canonical non-demo production bootstrap now requires both metric and Loki activation and injects verified Loki evidence into `IncidentService`.

## Run log — 2026-09-07 — dual evidence activation and canonical correlated production bootstrap

### Inspected at start

Read `progress.md` completely before selecting work. Inspected current `main`, especially:

- `runtime/activation.py`
- `runtime/onboarding.py`
- `runtime/preflight.py`
- `runtime/log_evidence.py`
- `runtime/mcp_log_client.py`
- `runtime/investigator.py`
- `runtime/incident_service.py`
- `runtime/bootstrap.py`
- `runtime/tests/test_activation.py`
- `runtime/tests/test_bootstrap.py`
- root `README.md`

The highest-value gap was exactly the prior handoff: Loki correlation existed but production startup still pinned only Prometheus, so enforcing correlated mode would have allowed Loki datasource/policy drift after onboarding.

### Exact changes made

Added `runtime/log_activation.py`:

- defines the canonical log-contract payload from StageGuard's existing trusted `TelemetryProfile`, bounded five-minute window, maximum eight lines, causal evidence class, and `packet_loss_alarm` event identity;
- hashes that exact contract with deterministic canonical JSON;
- adds `LogPreflightResult` and a one-query `preflight_loki()` path;
- healthy/empty Loki results can pass because onboarding is proving the evidence plane, not requiring an active incident;
- truncated preflight results fail closed;
- returned production/uplink scope drift fails closed;
- creates a time-bounded `LogActivationRecord` only after successful preflight;
- pins both exact log-contract SHA-256 and Loki datasource identity SHA-256;
- supports strict JSON persistence/loading and runtime verification;
- rejects contract drift, datasource drift, future-dated records, stale records, malformed preflight digests, and TTLs beyond seven days.

Updated `runtime/preflight.py`:

- now opens both official Grafana MCP evidence adapters;
- retains the exact eight-read Prometheus preflight;
- adds exactly one bounded Loki causal-query preflight;
- reports metric and Loki readiness separately plus one combined `ready` result;
- supports `--log-activation-output` alongside the existing `--activation-output`;
- writes neither evidence-plane activation unless that plane's own preflight passes.

Updated `runtime/bootstrap.py`:

- added `--log-activation`;
- non-default production profiles now require both metric and Loki activation artifacts;
- constructs the actual `McpLokiLogClient` for production and verifies the activation against that client's configured datasource UID;
- metric identity remains derived from the actual `McpPrometheusMetricClient` instance;
- passes the verified Loki client + activation to `IncidentService`;
- `RuntimeBundle` owns and closes the Loki client lifecycle;
- demo mode remains the explicit metric-only local exception unless a valid log activation is intentionally supplied;
- production remediation remains disabled by default and retains separate credentials/opt-in.

Updated `runtime/incident_service.py`:

- accepts a log client only together with a log activation record;
- automatically uses `investigate_with_log_corroboration()` when the verified log plane is configured;
- keeps metric-only investigation for the deterministic demo/direct unit use;
- adds `evidence_mode` to investigation audit metadata;
- adds only bounded, non-secret Loki activation hashes to audit metadata: contract hash, datasource hash, and preflight digest;
- does not copy raw production log lines into lifecycle audit metadata.

Updated `runtime/tests/test_bootstrap.py`:

- added a deterministic `FakeLogs` evidence client;
- production tests now create both activation artifacts;
- added explicit refusal coverage when the log activation is missing;
- added actual-Loki-datasource drift rejection;
- verifies production runtime owns/injects the correlated log client;
- retained non-loopback auth, safe disabled remediation, explicit write-settings, allowlisted transport, and demo write-refusal coverage under the stricter bootstrap.

Added `runtime/tests/test_log_activation.py`:

- healthy empty-window preflight + activation round trip;
- exactly one policy-owned preflight query;
- truncation refusal;
- returned production-scope drift refusal;
- Loki datasource drift rejection;
- semantic contract drift rejection;
- activation expiry rejection.

Updated root `README.md`:

- production architecture now shows both evidence-plane preflights/activation records;
- documented the healthy-empty Loki preflight semantics;
- documented canonical `--log-activation` startup requirement;
- updated production and remediation startup examples;
- removed the obsolete note that Loki correlation was not yet canonical.

### Commits produced this run

- `0427eb96` — pin Loki evidence contract for production activation
- `73d12c8d` — require correlated Loki investigation when configured
- `2c9cbfdd` — make pinned Loki corroboration canonical in production bootstrap
- `c2b8230f` — preflight and pin both Prometheus and Loki evidence planes
- `e523e710` — cover dual evidence activation in production bootstrap
- `e41f9302` — test Loki activation and bounded preflight invariants
- `59de74d6` — document pinned metric and Loki production evidence activation
- `592fd13d` — tighten Loki activation round-trip test

### Tests / checks / results

Attempted a clean checkout and deterministic compile/test path with:

```bash
git clone https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard
cd /tmp/stageguard
python -m compileall -q runtime
```

The execution container still fails DNS resolution for `github.com`, so the checkout could not materialize and the Python suite could not start. The new tests are therefore **not claimed as passing** in this environment.

No GitHub Actions workflow was created, triggered, or rerun as a substitute. No Grafana, Loki, Gemini, Google Cloud, operator, or production-remediation credential was used.

### Decisions made

1. **Metric and Loki activations remain separate artifacts.** This avoids silently changing the already-stable metric activation schema while still requiring both evidence planes atomically at canonical production bootstrap.
2. **A Loki onboarding query need not find an incident.** Zero matching causal logs is normal in a healthy production; onboarding proves query execution, bounds, datasource identity, and scope contract.
3. **Production correlation is now canonical.** Non-demo bootstrap always constructs/validates Loki and `IncidentService` automatically uses metric+Loki investigation.
4. **Metrics still originate the diagnosis.** Loki executes only after the six metric slots diagnose; it cannot manufacture or override a root cause.
5. **Both datasource identities come from live adapter configuration.** Callers cannot provide a second runtime datasource string that differs from the client actually used.
6. **Audit stores activation provenance, not raw logs.** This preserves evidence-chain identity without unnecessarily duplicating production log content into durable lifecycle audit records.
7. **Write capability was not expanded.** Production remediation remains disabled unless explicitly opted in with a separate endpoint and credential.

### Current blockers / unknowns

- Full deterministic Python suite is unexecuted here because the execution container cannot resolve GitHub for a local checkout.
- Full Compose startup and official MCP metric/Loki acceptance remain unverified on a Docker-capable host.
- The Loki parser/preflight have not yet been exercised against a live `query_loki_logs` response from the pinned runtime image.
- OIDC/IAP, Gemini explanation/orchestration, operator UI, durable tamper-resistant audit storage, and Google Cloud deployment remain implementation gates.

## Single best next step

**Add the first Gemini incident-commander layer above the now-pinned deterministic metric+Loki safety core: give Gemini only a bounded, structured `IncidentReport`/tool outcome surface for explanation and operator communication, require the deterministic core to remain authoritative for diagnosis/approval/remediation, add a credential-free deterministic model fixture plus prompt-injection/unsafe-action tests, and keep direct infrastructure-write authority out of the model boundary.**
