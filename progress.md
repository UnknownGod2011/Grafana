# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, strict evidence parsing, evidence-unavailable abstention, fail-closed HTTP/operator handling, explicit no-replay reconciliation for post-remediation persistence uncertainty, and versioned telemetry onboarding/preflight.

Core invariants retained:
- Grafana/MCP is read-only evidence access; infrastructure write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove recovery.
- Durable checkpoint/audit failures fail closed and uncommitted state is not operator-visible lifecycle authority.
- Once provider dispatch may have occurred, persistence uncertainty blocks replay.
- Browser/API surfaces must not expose provider failure detail or turn evidence loss into actionable state.
- Expected evidence transport/protocol/datasource failures cross runtime boundaries as `EvidenceUnavailable`; provider exception text is diagnostic-only and must not be copied into operator/onboarding results.
- Unexpected programming/policy exceptions must fail loudly rather than being downgraded to telemetry unavailability.
- Private Cloud Run metric requests reject redirects and keep token audience/target boundaries explicit.
- Runtime metric readiness requires an unambiguous StageGuard safety sentinel, not merely HTTP 200.
- A metrics bridge bound beyond loopback requires explicit network-bind opt-in, inbound bearer authentication, strict bearer-token syntax, and a minimum 32-character credential.
- The reference Grafana MCP dependency is pinned to `grafana/mcp-grafana:1.4.1`; server-side write/proxy restrictions are regression-locked; the live smoke rejects any advertised MCP tool that is not explicitly annotated `readOnlyHint=true`.
- Grafana MCP smoke requests are time-bounded, stdout JSON-RPC frames are individually bounded, strict framing/response integrity fails closed, and pending stdout frames are held in a fixed-capacity queue.
- Cloud Run remediation/recovery execution watchdog configuration is bounded to 1-600 seconds.
- Cloud Run checkpoint HMAC keys are bounded to 32-512 UTF-8 bytes and reject leading/trailing whitespace or control characters before runtime composition.
- The Cloud Run deployment helper has a hermetic shell regression boundary that rejects unsafe watchdog values before any `gcloud` invocation.
- Telemetry profiles require independent healthy comparators: `healthy_uplink` cannot equal `affected_uplink`, `healthy_peer_feeds` cannot include the affected feed, and healthy peer feeds cannot contain duplicates.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest checkpoint/acceptance hardening.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires an executable live smoke before a production-ready claim.
- Recent MCP hardening added request deadlines, strict JSON-RPC framing/response-ID validation, a 1,048,576-character frame cap, and a 16-frame pending stdout queue; the actual repository regression modules still need a runnable checkout.

## Recent completed work

### Cloud Run production safety bounds
- Bounded `STAGEGUARD_REMEDIATION_EXECUTION_MAX_SECONDS` to 1-600 seconds in runtime and deployment helper.
- Bounded checkpoint HMAC keys to 32-512 UTF-8 bytes and reject malformed boundary/control characters.
- Added focused Cloud Run entrypoint and hermetic deploy-script regressions.

### Telemetry mapping safety
- Enforced independent healthy comparator mappings.
- Reconciled runtime documentation with the Grafana MCP 1.4.1 baseline and current safety controls.

## Run log — 2026-09-12 — onboarding evidence-error boundary

### Inspected at start

Read this `progress.md` completely before deciding what to change. Inspected repository metadata and reviewed:
- `runtime/onboarding.py`
- `runtime/tests/test_onboarding.py`
- `runtime/telemetry.py`
- `runtime/investigator.py`
- `runtime/evidence_errors.py`
- `ARCHITECTURE.md`

Also checked current Prometheus/RE2 documentation while evaluating the telemetry-query construction boundary. No unrelated repository, GitHub Actions workflow, cloud resource, Grafana instance, Gemini endpoint, or remediation provider was modified.

### Findings

1. `preflight_telemetry()` caught every `Exception`, which allowed programming/policy failures to be silently downgraded into an ordinary non-ready telemetry slot.
2. The same path copied `type(exc).__name__` and `str(exc)` into `PreflightSlot.detail`. Adapter/provider exceptions may contain endpoint URLs, credentials, backend details, or other integration-sensitive text.
3. This behavior contradicted the repository's existing `EvidenceUnavailable` contract, whose explicit purpose is to separate expected evidence-source failures from programming/policy errors and keep provider exception text local-only.
4. The investigator already follows the safer contract; onboarding was an inconsistent boundary.

### Exact changes made

#### 1. Hardened onboarding to the adapter-neutral evidence contract

Commit: `18bd60b31ad2ac9ab3cf71d0345d76b0c446114f`

`runtime/onboarding.py` now:
- imports and catches only `EvidenceUnavailable` for expected telemetry-source failure;
- records the stable generic detail `evidence source unavailable` rather than provider exception text;
- continues checking the remaining bounded onboarding slots after expected evidence unavailability;
- allows unexpected programming/policy exceptions to propagate immediately instead of misclassifying them as telemetry health;
- documents the boundary directly in `preflight_telemetry()`.

#### 2. Added focused regression coverage

Commit: `5f3d2db3d477bf02c779f8a7c44c981fddff17a3`

`runtime/tests/test_onboarding.py` now verifies:
- an `EvidenceUnavailable` containing a secret-bearing provider URL is redacted from serialized preflight output;
- expected evidence unavailability leaves activation non-ready and still checks all eight bounded slots;
- an unexpected `AssertionError` propagates and stops the preflight instead of being downgraded.

### Checks / results

- Authenticated GitHub inspection and both repository writes succeeded.
- A fresh executable checkout was attempted with `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git`; the runner again failed with `Could not resolve host: github.com` before repository tests could execute.
- No GitHub Actions workflow was triggered or rerun as a workaround.
- Python 3.13 behavior used during investigation confirmed `re.escape()` behavior for the default peer labels; no telemetry-regex change was made without stronger evidence that the current RE2 pattern is invalid.
- Because the repository checkout remains unavailable, `python -m unittest runtime.tests.test_onboarding runtime.tests.test_telemetry -v` has not yet been executed against the committed tree. There is no new repository-suite green claim.

### Decisions

1. Reuse `EvidenceUnavailable` consistently at onboarding and investigation boundaries rather than creating a second error taxonomy.
2. Treat provider exception messages as local diagnostics, not serializable operator/onboarding state.
3. Fail unexpected programming and policy exceptions loudly; an onboarding preflight must not make broken code look like ordinary datasource unavailability.
4. Keep the preflight bounded at exactly eight read-only semantic checks and continue evaluating remaining slots only for expected evidence-source failure.
5. Continue avoiding noisy GitHub Actions solely to work around the transient runner DNS failure.

### Blockers / unknowns

- `runtime.tests.test_onboarding` and `runtime.tests.test_telemetry` need execution from an actual checkout.
- `runtime.tests.test_cloudrun_entrypoint` and `runtime.tests.test_deploy_cloud_run_script` still need a current repository run.
- `runtime.tests.test_mcp_smoke_timeout`, `runtime.tests.test_mcp_smoke_surface`, and `runtime.tests.test_observability_image_pins` still need an actual repository run.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required before calling that dependency baseline production-ready.
- The strengthened Cloud Run bridge six-module set still needs an executable run.
- The execution-reconciliation/operator/Playwright safety set still needs a current run.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**When executable checkout is available, run `python -m unittest runtime.tests.test_onboarding runtime.tests.test_telemetry runtime.tests.test_cloudrun_entrypoint runtime.tests.test_deploy_cloud_run_script -v` first. If clean, run the MCP timeout/surface/image-pin regressions and the live pinned Grafana MCP 1.4.1 smoke; then proceed to the private `ADC -> Cloud Run /metrics -> authenticated bridge -> Prometheus up: 1 -> 0 -> 1` acceptance.**
