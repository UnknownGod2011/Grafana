# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the indispensable runtime evidence plane. The working vertical slice remains: deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, restart reconciliation, and a same-origin operator cockpit.

Core invariants:
- Grafana is the evidence plane; infrastructure write credentials stay isolated from Grafana/MCP access.
- Gemini is optional/advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact evidence revision.
- Remediation success is never inferred from an action response; fresh Grafana telemetry must prove recovery.
- Authenticated checkpoints and audit integrity fail closed.

## Run log — 2026-09-10 — watchdog HTTP observability and runtime configuration

### Inspected at start

Read `progress.md` completely before deciding work. Inspected the active remediation/watchdog path and HTTP/bootstrap composition:
- `runtime/anchored_execution_safety.py`
- `runtime/api.py`
- `runtime/bootstrap.py`
- `runtime/cloudrun_entrypoint.py`
- `runtime/tests/test_api_concurrency.py`
- `runtime/tests/test_cloudrun_entrypoint.py`

Confirmed the production service already tracks a monotonic active execution age and fails `checkpoint_state()` closed to `execution_uncertain` after the configured bound. The remaining gap was operator/runtime visibility: the age and deadline were not explicit in `/metrics` or `/readyz`, lifecycle responses did not expose the bounded watchdog view, and the 60-second limit could not be configured through bootstrap/Cloud Run process configuration.

### Exact changes made

Updated `runtime/api.py`:
1. Added a bounded `_remediation_execution_observability()` adapter around the service watchdog method.
2. The adapter exposes only `active`, `age_seconds`, `max_seconds`, and `deadline_exceeded`; provider URLs, operation IDs, targets, exceptions, credentials, and arbitrary service fields are never forwarded.
3. Missing watchdog support remains backward compatible and reports an inactive zeroed view.
4. Malformed/exceptional watchdog output fails closed to `deadline_exceeded=true` with zeroed numeric fields rather than leaking exception/provider detail.
5. Authenticated lifecycle responses now include a `remediation_execution` object.
6. `/readyz` now includes `checks.remediation_execution_deadline=ok|exceeded`; an exceeded or malformed watchdog forces `ready=false` independently of the checkpoint-derived signal.
7. The generic readiness exception fallback now includes `remediation_execution_deadline=failed`.
8. `/metrics` now exports four fixed-cardinality gauges:
   - `stageguard_remediation_execution_active`
   - `stageguard_remediation_execution_age_seconds`
   - `stageguard_remediation_execution_max_seconds`
   - `stageguard_remediation_execution_deadline_exceeded`

Updated `runtime/tests/test_api_concurrency.py`:
1. Added a thread-safe fake monotonic clock and configured a deterministic 5-second watchdog.
2. While the blocking remediation fake is active, the HTTP test now verifies lifecycle watchdog state, readiness deadline state, and all four Prometheus gauges.
3. Advances monotonic time past the deadline without sleeping and verifies `/readyz` returns HTTP 503 with `checkpoint=execution_uncertain` and `remediation_execution_deadline=exceeded`.
4. Verifies metrics report age 6.0, configured max 5.0, and deadline exceeded while the provider remains blocked.
5. Retains the single-dispatch/competing-mutation assertions and verifies watchdog metrics return inactive after successful telemetry-verified recovery.

Added `runtime/tests/test_api_execution_watchdog.py`:
- verifies backward compatibility for runtimes without watchdog support;
- verifies normalization of valid numeric watchdog output;
- verifies arbitrary/provider-specific fields are dropped;
- verifies malformed booleans, negative/NaN ages, non-positive/infinite maxima, missing dictionaries, and runtime exceptions all fail closed;
- verifies synthetic provider/secret text from an exception is not surfaced.

Updated `runtime/bootstrap.py`:
1. Imports the service's canonical `DEFAULT_MAX_REMEDIATION_EXECUTION_SECONDS` constant.
2. Added `remediation_execution_max_seconds` to `build_runtime()` with the canonical default.
3. Passes the configured value to `AnchoredExecutionSafeIncidentService`, which retains the finite/positive validation boundary.
4. Added CLI option `--remediation-execution-max-seconds` and wired it through `main()`.

Updated `runtime/cloudrun_entrypoint.py`:
1. Added `STAGEGUARD_REMEDIATION_EXECUTION_MAX_SECONDS` process configuration.
2. Defaults to the canonical 60-second service value through `bootstrap.DEFAULT_MAX_REMEDIATION_EXECUTION_SECONDS` rather than duplicating a numeric default.
3. Rejects blank, zero, negative, NaN, infinity, and non-numeric values before bootstrap startup.
4. Always passes the resolved value as `--remediation-execution-max-seconds`, keeping the Cloud Run composition explicit and inspectable.
5. Did not add any environment switch that enables production remediation; write capability remains an explicit alternate deployment/process decision.

Updated `runtime/tests/test_cloudrun_entrypoint.py`:
- asserts the default Cloud Run watchdog is 60.0 seconds;
- verifies a custom finite positive value is forwarded;
- verifies blank/zero/negative/NaN/infinite/non-numeric values fail closed.

Commits this run:
- `da09ed51e3b818f951f0249b3b362b8dff3c59e2` — expose remediation watchdog through readiness and metrics
- `d34e5da8a7669d034a1be5c3f195348fe53739d4` — cover remediation watchdog HTTP observability
- `d0ee9e02e84be1b949937b792e87d84ed4674dea` — test fail-closed watchdog API sanitization
- `63ee41a05512eca0cf923f72d0c0e187aa71677e` — make remediation watchdog duration configurable
- `ed24d3ca185cfb276a9720335591c2819663d17d` — wire Cloud Run remediation watchdog configuration
- `246bce50b312231e2241daab09c19ca95ec33ca2` — test Cloud Run watchdog configuration

### Tests / checks / results

Validation performed in this run:
- Re-fetched the committed `runtime/api.py` watchdog/readiness/metrics section and visually verified the fixed-shape sanitization, readiness gating, and metric names after the write.
- Re-fetched `runtime/tests/test_api_execution_watchdog.py` after creation and verified its committed malformed-state/secret-redaction cases.
- Preserved the prior HTTP concurrency harness rather than introducing timing sleeps; the new deadline transition is driven by an injected monotonic clock.
- Preserved the canonical service-side finite/positive validation boundary while also failing Cloud Run startup earlier for invalid process configuration.
- Confirmed no GitHub Actions workflow was created, triggered, or rerun.

The exact committed Python tests still could not be executed from a repository checkout in this automation environment because `github.com` DNS resolution fails for `git ls-remote`/`git clone`. Therefore no new green-suite claim is made. The changed files were re-read through the GitHub connector, but that does not replace executable test coverage.

No external Grafana instance, MCP server, Google Cloud project, Cloud Run service, Secret Manager secret, IAM policy, Gemini endpoint, checkpoint object, or remediation endpoint was modified.

### Decisions made

1. Watchdog telemetry is treated as a safety signal, not informational-only telemetry: malformed data fails readiness closed.
2. The HTTP surface exports only a fixed, provider-detail-free schema. Arbitrary keys returned by a service implementation are discarded.
3. Execution age is a gauge based on the service's monotonic timer; it is zero when inactive and cannot reveal wall-clock execution timestamps.
4. Deadline readiness is explicit even though checkpoint state also becomes `execution_uncertain`, so operators can distinguish a live over-deadline call from other durable reconciliation conditions.
5. Cloud Run exposes the watchdog duration without creating a remediation enablement switch. The standard production entrypoint still keeps remediation writes disabled.
6. The bootstrap uses the service's canonical default instead of duplicating `60.0`, reducing drift between runtime and deployment behavior.

### Current blockers / unknowns

- `runtime.tests.test_api_concurrency`, `runtime.tests.test_api_execution_watchdog`, `runtime.tests.test_cloudrun_entrypoint`, and the focused bootstrap/API/runtime suite still need execution from a runnable checkout.
- The production Cloud Run deploy helper does not yet expose `STAGEGUARD_REMEDIATION_EXECUTION_MAX_SECONDS` as an operator-controlled deployment value; the entrypoint supports it, but standard deploy configuration currently receives the safe default unless the environment is set another way.
- Grafana dashboards/alerts do not yet visualize or alert on the new active/age/deadline gauges.
- A hung Python provider call still cannot be forcibly interrupted safely; readiness is withdrawn, but process replacement remains the supervisor/platform responsibility.
- The exact Cloud Storage object Policy Troubleshooter tuple still needs one authorized disposable-project acceptance run.
- Gemini deployment doctor and real Vertex AI acceptance smoke still need authorized disposable-project credentials.

## Single best next step

**Integrate the new watchdog gauges into the actual Grafana runtime observability layer: locate the provisioned StageGuard dashboard/alerting configuration, add panels for active remediation age versus configured maximum and a high-signal alert on `stageguard_remediation_execution_deadline_exceeded == 1`, then expose the watchdog duration through the safe Cloud Run deploy helper so real deployments can tune it without bypassing validation. Add static/config regression coverage without triggering GitHub Actions.**

## Retained production hardening

- Cloud Run production deployment uses authenticated GCS checkpoints rather than silent ephemeral/no-checkpoint state.
- Runtime checkpoint HMAC keys are Secret Manager supplied and at least 32 UTF-8 bytes.
- Checkpoint object validation is byte-accurate and aligned across deploy helper, deployment doctor, and runtime.
- Cloud Run deployment rejects malformed/injected comma-delimited environment and secret mapping inputs before `gcloud`.
- Google Cloud project/region/service/image identifier grammar is centralized and shared by the deploy helper and deployment doctor.
- Live deployment preflight verifies the configured Cloud Run region against the current provider-reported region catalog.
- Runtime MCP launcher parsing is centralized and cross-platform.
- Readiness validates local activation/pin trust before spawning/querying Grafana MCP.
- Deployment-doctor gcloud process failures fail closed with probe-specific sanitized diagnostics.
- Production remediation releases the lifecycle lock across provider contact and Grafana recovery polling while blocking competing mutations with an explicit in-flight guard.
- HTTP concurrency coverage protects incident/readiness/metrics visibility and single-dispatch semantics while remediation is active.
- Active remediation has a monotonic bounded watchdog; exceeding it withdraws readiness without replaying or cancelling the action.
- Watchdog state is now exported through authenticated lifecycle state, explicit readiness, and fixed-cardinality Prometheus gauges.
- The watchdog duration is configurable through runtime bootstrap and validated Cloud Run process configuration.
- Gemini acceptance smoke defaults to zero model calls and requires explicit `--execute`.
- Standard Cloud Run deployment keeps production remediation disabled.

## Validation baseline retained

- Local onboarding doctor: 8 tests passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable run: 81/81 passed.
- Historical full suite baseline: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Live Docker rehearsal: PASS twice consecutively.
- Official Grafana MCP read-only smoke path: PASS using `grafana/mcp-grafana:1.3.0`.
- Incident flow: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.
