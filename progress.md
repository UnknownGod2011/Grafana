# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence plane. The current vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, restart reconciliation, operator UI, deployment hardening, runtime watchdog observability, authenticated Cloud Run metrics ingestion, stale-telemetry detection, scrape-health detection, credential-free outage rehearsal, pinned Grafana/Prometheus acceptance images, runtime-version attestation, strict Prometheus acceptance parsing, a cardinality-ambiguity probe, and a fail-closed Grafana MCP metric evidence boundary.

Core invariants:
- Grafana/MCP is read-only evidence access; infrastructure write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Approval is exact-revision-bound and single-use.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove it.
- Durable checkpoint/audit integrity failures fail closed.
- A healthy watchdog value is trustworthy only while the observability path is delivering fresh samples.
- Loss of observability must never be reclassified as a positive remediation deadline breach.
- Ambiguous, malformed, nonnumeric, or non-finite Prometheus evidence must never be interpreted as healthy incident evidence.
- Metrics bridge process liveness must not be confused with authenticated upstream readiness.
- Prometheus scrape failure is a transport/collection warning, not evidence that a remediation deadline was exceeded.

## Run log — 2026-09-11 — Grafana MCP metric evidence hardening

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected the repository/default branch and the evidence path, including:
- `runtime/mcp_metric_client.py`
- `runtime/mcp_log_client.py`
- `runtime/tests/test_mcp_metric_client.py`
- `runtime/investigator.py`
- `docker-compose.yml`
- `ARCHITECTURE.md`

The prior run's best next step was to execute the pinned Docker rehearsal and, if execution remained unavailable, move away from acceptance scaffolding toward a production integration gap. Because the execution container still cannot resolve GitHub, this run shifted to official Grafana MCP incident-evidence hardening rather than adding more rehearsal-only code.

### Research / current external references

Checked current official Grafana MCP documentation before changing the adapter:
- Grafana MCP introduction: https://grafana.com/docs/grafana/latest/developer-resources/mcp/introduction/
- Grafana MCP configuration: https://grafana.com/docs/grafana/latest/developer-resources/mcp/configure/
- MCP tools/RBAC reference: https://grafana.com/docs/grafana/latest/developer-resources/mcp/reference/mcp-tools-table/
- tool enable/disable and `--disable-write`: https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/oss-mcp/configure/enable-and-disable-tools/

The repository already starts the reference MCP service with `--disable-write`, `--enabled-tools datasource,prometheus,loki`, `--disable-proxied`, and a bounded Loki limit. That remains the correct defense-in-depth posture: server-side write disabling plus client-side tool verification.

### Exact changes made

#### Hardened `runtime/mcp_metric_client.py`

The previous MCP metric parser used `float(value)`, which accepts `NaN` and infinities. That was inconsistent with StageGuard's newer acceptance-safety rules and could allow a non-finite Prometheus sample to enter diagnosis as if it were ordinary numeric evidence.

Changes:
- imported `math` and changed numeric coercion to require `math.isfinite()`;
- `NaN`, `Inf`, `+Inf`, and `-Inf` now raise `McpMetricError`;
- preserved strict duplicate-series rejection instead of guessing among multiple series;
- require a non-empty Prometheus datasource UID;
- require non-empty PromQL before attempting MCP connection/query execution;
- validate `tools/list` is an object containing `tools[]`;
- validate tool annotations are an object and `query_prometheus` advertises `readOnlyHint=true`;
- validate the `tools/call` result itself is an object before parsing it;
- updated the parser contract/docstring so only exactly one finite numeric observation is considered usable evidence.

Commit:
- `6a42ca3904a8c6a1431cc9e7b86693a576fe9ddd` — harden Grafana MCP metric evidence parsing

#### Expanded `runtime/tests/test_mcp_metric_client.py`

Added focused dependency-free regression cases for:
- `NaN`, `Inf`, `+Inf`, and `-Inf` in vector results;
- the same non-finite values in scalar results;
- blank datasource UID rejection;
- blank PromQL rejection before MCP connection;
- non-object tool result rejection.

Existing tests continue to cover finite scalar/vector parsing, empty-vector missing evidence, structured content, duplicate-series rejection, tool errors, and nonnumeric samples.

Commit:
- `e087ac1f9a39b6f1a5e4a4dc295482df902bfced` — test fail-closed MCP metric evidence handling

#### Added operator/developer evidence-safety documentation

Created `docs/grafana-mcp-evidence-safety.md` documenting:
- the least-privilege official Grafana MCP deployment shape;
- the exact metric evidence contract;
- the existing bounded Loki evidence contract;
- the separation between evidence credentials and remediation credentials;
- regression expectations for future MCP adapter changes;
- official Grafana MCP documentation links.

Commit:
- `63dd7358331ddcc7b4081afa8278c5bc763f6daa` — document Grafana MCP evidence safety contract

### Checks / results

- Re-fetched the committed `runtime/mcp_metric_client.py` from `main` and verified the finite-number guard, strict tools-list checks, datasource validation, and exact single-series policy are present.
- Attempted an executable checkout and focused unit test with:

```bash
git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard
cd /tmp/stageguard
python -m unittest runtime.tests.test_mcp_metric_client
```

The container failed before checkout with `Could not resolve host: github.com`; therefore no green unittest claim is made for the newly committed tests.
- No GitHub Actions workflow was created, modified, triggered, or rerun.
- No external Grafana/Grafana Cloud, GCP/IAM/Cloud Run, Gemini, checkpoint, or remediation resource was changed.

### Decisions

1. Treat non-finite Prometheus values as unusable incident evidence, not merely unusual numeric values.
2. Keep `None` reserved for a legitimate empty-vector/missing-evidence result; malformed/tool-error/non-finite cases remain explicit errors so they cannot be confused with ordinary telemetry absence.
3. Reject ambiguous vectors at the MCP boundary. StageGuard's policy-selected instant queries are required to reduce to at most one authoritative series.
4. Preserve server-side `--disable-write` even though the clients call only query tools. Tool annotations are an additional runtime assertion, not the sole write-safety mechanism.
5. Validate user/config inputs before opening an MCP process when possible, reducing unnecessary subprocess/tool activity and making failures deterministic.

### Blockers / unknowns

- `runtime.tests.test_mcp_metric_client` still needs execution from a runnable checkout.
- The complete credential-free Docker watchdog rehearsal still needs to run against pinned Prometheus 3.13.3 and Grafana 13.2.1.
- The authenticated metrics bridge still needs a disposable-project acceptance against a private Cloud Run StageGuard service using a least-privilege invoker identity.
- Container image digests remain uncommitted because authoritative registry digests have not been verified through the available execution path.
- The historical full-suite failures/errors have not yet been re-triaged; no full-suite green claim exists.

## Single best next step

**Harden the incident orchestration boundary so Grafana MCP transport/protocol failures become an explicit structured `abstain`/evidence-unavailable outcome instead of bubbling into an opaque request failure, while still not swallowing programming errors. Add a small adapter-neutral evidence-collection error contract, preserve which bounded evidence slot failed without exposing credentials/tool payloads, and regression-test that no approval/remediation path can be reached from a partial or failed MCP evidence collection. If a runnable checkout becomes available first, execute `python -m unittest runtime.tests.test_mcp_metric_client runtime.tests.test_mcp_log_client runtime.tests.test_investigator runtime.tests.test_correlated_investigator` and the pinned Docker observability rehearsal before further integration work.**

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from last executable run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively; it predates the newest ordered scrape/stale outage acceptance path, explicit image pins, runtime-version attestation, strict Prometheus safety parsing, live ambiguity probe, bridge readiness work, and current MCP finite-evidence hardening.
- Official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0` before the current MCP finite-evidence hardening.
- Incident flow baseline: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.
