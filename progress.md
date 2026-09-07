# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable safety core currently covers:

`versioned telemetry mapping → eight-read metric preflight → hash-pinned/time-bounded activation → official Grafana MCP metric adapter → bounded six-read metric investigation → optional bounded official Grafana MCP Loki corroboration → activation-enforced audited IncidentService → trusted operator identity → revision-bound approval → governed allowlisted remediation → explicit credential-isolated HTTPS transport → bounded two-read recovery verification`

Core invariants:

- Grafana is the evidence plane; infrastructure write credentials remain separate.
- Callers never provide raw PromQL, raw LogQL, datasource IDs, remediation actions, targets, endpoints, or credentials through the incident API.
- Production metric mappings are explicit and validated; omitted values never inherit demo scope.
- Metric activation preflight performs exactly six investigation reads plus two recovery reads and requires exactly one numeric sample per slot.
- Activation artifacts bind the validated metric profile and metric datasource identity by SHA-256 and expiry.
- Non-default production profiles cannot construct `IncidentService` without a matching activation record.
- The metric investigator diagnoses only from six fixed semantic slots.
- The new correlated investigator performs one additional bounded Loki query only after metrics independently support the configured uplink-loss diagnosis.
- Missing Loki corroboration is not treated as negative evidence; it causes abstention. Truncated, scope-drifted, or event-drifted log results are ambiguous and also cause abstention.
- Official Grafana MCP Loki results are bounded, parsed fail-closed, and preserve timestamp/label/structured-metadata/parser provenance without exposing arbitrary query execution to callers.
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
- Canonical production bootstrap wiring mapping + activation + MCP metric datasource + audit + auth + service + bind policy.
- Governed production remediation policy with deterministic operation identity, bounded retry/timeout semantics, and non-secret audit metadata.
- Concrete HTTPS remediation transport with separate write credential and server idempotency contract.
- Loopback-only reference remediation receiver proving exact-retry idempotency without real infrastructure mutation.
- Bounded semantic Loki corroboration contract generated from trusted telemetry scope rather than caller LogQL.
- Official Grafana MCP `query_loki_logs` adapter with read-only-tool verification, strict response parsing, bounds, traces, and conservative truncation detection.
- Correlated investigator mode in which Loki may only corroborate an already-supported metric diagnosis and missing/ambiguous logs fail closed.

## Run log — 2026-09-07 — bounded Loki corroboration

### Inspected at start

Read `progress.md` completely before selecting work. Inspected current `main`, especially:

- `runtime/investigator.py`
- `runtime/incident_service.py`
- `runtime/mcp_metric_client.py`
- `runtime/telemetry.py`
- `runtime/tests/`
- root `README.md`

Also verified the current official Grafana MCP documentation/source for Loki. The official server exposes `query_loki_logs` as a read-only datasource query tool. Its current contract accepts `datasourceUid`, `logql`, bounded time range, limit, direction, query type, and output format; current responses include per-entry timestamp/line/labels plus optional structured metadata/parser labels and query metadata including `resultsTruncated`. The MCP server also has a configurable `--max-loki-log-limit` and query-cost guardrail support.

### Exact changes made

Added `runtime/log_evidence.py`:

- defined typed `LogRecord`, `LogQueryResult`, `LogQueryClient`, and `LogCorroboration` contracts;
- added one policy-owned semantic LogQL builder for the configured production + affected uplink;
- the query requires structured JSON event identity `packet_loss_alarm` rather than free-text keyword matching;
- caller input cannot supply arbitrary LogQL;
- bounded the causal corroboration window to `now-5m..now` and maximum eight returned lines;
- requires returned stream labels to agree with configured production/uplink scope;
- verifies event identity from parsed labels, structured metadata, or JSON log body;
- returns `missing` for no corroborating log, `ambiguous` for truncation/scope/event disagreement, and `corroborated` only for complete consistent evidence.

Added `runtime/mcp_log_client.py`:

- introduced `McpLokiLogClient` backed by the same official Grafana MCP stdio transport model used by metrics;
- verifies `query_loki_logs` exists and advertises `readOnlyHint=true` before use;
- sends fixed range-query semantics (`backward`, `range`, `full`) with a caller-independent datasource configuration;
- validates requested limits between 1 and 100;
- strictly parses JSON-text or structured MCP results;
- rejects malformed entries, non-string label maps, more rows than requested, inconsistent metadata counts, and malformed metadata;
- uses official `resultsTruncated` metadata when available;
- conservatively treats an older metadata-less response that exactly fills the requested limit as potentially truncated;
- records non-secret `LogQueryTrace` provenance: LogQL, effective time range, limit, latency, line count, truncation state.

Updated `runtime/investigator.py`:

- extended `IncidentReport` with optional typed `log_corroboration` provenance;
- preserved the original six-read metric-only `investigate()` behavior for compatibility;
- added `investigate_with_log_corroboration()`;
- Loki is queried only if all six metric slots already produce `diagnosed`;
- a missing, truncated, scope-inconsistent, or event-inconsistent Loki result converts that metric diagnosis to `abstain` with zero confidence;
- Loki can never override contradictory metrics or independently create a diagnosis;
- successful correlation preserves the metric hypothesis/confidence and records the log evidence in the report revision.

Added `runtime/tests/test_log_evidence.py` covering:

1. safe scope-bound LogQL generation and escaping;
2. successful single-query corroboration;
3. missing-log semantics;
4. truncation refusal;
5. production/uplink scope drift refusal;
6. event-identity drift refusal.

Added `runtime/tests/test_mcp_log_client.py` covering:

1. parsing official full Loki payloads and metadata;
2. conservative truncation for legacy metadata-less exact-limit results;
3. metadata/data count mismatch rejection;
4. non-string label rejection;
5. returned-row bound enforcement.

Added `runtime/tests/test_correlated_investigator.py` covering:

1. six metric reads + one Loki corroboration for a supported diagnosis;
2. missing Loki evidence forcing abstention;
3. truncated Loki evidence forcing abstention;
4. no Loki query when metrics already abstain.

### Commits produced this run

- `68f58b3f` — bounded semantic Loki corroboration
- `d0883aba` — official Grafana MCP Loki adapter
- `3b88b19e` — fail-closed metric + Loki investigator mode
- `3e8c935e` — log-evidence policy tests
- `e3c52bb0` — MCP Loki parser tests
- `fd720f37` — correlated-investigator tests

### Research / attribution

Implementation was checked against current official Grafana sources rather than a third-party Loki MCP server:

- Grafana MCP introduction and datasource capabilities: https://grafana.com/docs/grafana/latest/developer-resources/mcp/introduction/
- Grafana MCP tool enable/disable/read-only behavior: https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/oss-mcp/configure/enable-and-disable-tools/
- Official repository: https://github.com/grafana/mcp-grafana
- Current official Loki tool source: `tools/loki.go` in `grafana/mcp-grafana`

### Tests / checks / results

A clean checkout was attempted again with:

```bash
git clone https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard
```

The execution container still fails DNS resolution for `github.com`, so the checkout did not materialize and the deterministic Python suite could not be executed. Therefore these new tests are **not claimed as passing** in this environment.

No GitHub Actions workflow was created, triggered, or rerun as a substitute. No Grafana, Loki, Gemini, Google Cloud, operator, or production-remediation credential was used.

### Decisions made

1. **Logs corroborate; they do not originate the diagnosis.** This keeps the deterministic metric evidence policy authoritative and prevents a noisy log line from manufacturing a root cause.
2. **One semantic Loki query is the current budget.** It is executed only after six metric reads support the hypothesis, keeping query cost and evidence surface bounded.
3. **No arbitrary LogQL enters the incident API.** LogQL is generated from trusted configuration using the same production/uplink scope as metrics.
4. **Truncation is ambiguity.** StageGuard will not claim corroboration from a partial log set.
5. **Old MCP payloads fail conservatively.** If truncation metadata is absent and a response exactly fills the requested limit, StageGuard treats it as potentially incomplete.
6. **Log lines are evidence, not audit payloads.** The adapter/report can preserve evidence provenance, but future lifecycle audit integration should record bounded metadata/hashes rather than copying raw production logs into durable audit records.
7. **Production activation is not yet expanded to Loki in this run.** Enforcing correlated mode in canonical production bootstrap before pinning the Loki datasource + semantic log contract would create a configuration-drift gap, so that wiring is intentionally deferred rather than implemented unsafely.

### Current blockers / unknowns

- Full deterministic Python suite is unexecuted here because the automation container cannot resolve GitHub for a local checkout.
- Full Compose startup and official MCP Gate A remain unverified on a Docker-capable host.
- The new Loki parser has not yet been exercised against a live `query_loki_logs` response from the pinned runtime image.
- Production activation currently pins the metric telemetry profile + Prometheus datasource only; Loki datasource identity and log-corroboration policy are not yet activation-pinned.
- Canonical `runtime/bootstrap.py` therefore still uses the existing metric-only investigator path; correlated investigation exists as an implemented/tested-by-contract mode but is not yet the mandatory production path.
- OIDC/IAP, Gemini explanation/orchestration, operator UI, durable tamper-resistant audit storage, and Google Cloud deployment remain implementation gates.

## Single best next step

**Extend production onboarding/activation to include the Loki datasource identity and the exact semantic log-corroboration contract, preflight one bounded causal Loki query, then wire `McpLokiLogClient` + `investigate_with_log_corroboration()` into canonical production bootstrap. This makes metric+log correlation enforceable in real deployments without introducing unpinned evidence configuration.**
