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
- The private Cloud Run acceptance harness now requires one bounded selector-safe Prometheus job identity before any upstream or Docker action; the same validated identity is used in generated YAML and exact PromQL selectors.
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

### Telemetry mapping and onboarding safety
- Enforced independent healthy comparator mappings.
- Reconciled runtime documentation with the Grafana MCP 1.4.1 baseline and current safety controls.
- Hardened onboarding to catch only `EvidenceUnavailable`, redact provider detail from operator-visible preflight state, and fail unexpected programming/policy exceptions loudly.

## Run log — 2026-09-12 — private acceptance job identity boundary

### Inspected at start

Read this `progress.md` completely before deciding what to change. Inspected repository metadata and reviewed:
- `runtime/cloud_run_metrics_acceptance.py`
- `runtime/cloud_run_metrics_bridge.py`
- `runtime/tests/test_cloud_run_metrics_acceptance.py`
- current runtime/test directory structure

No unrelated repository, GitHub Actions workflow, cloud resource, Grafana instance, Gemini endpoint, IAM binding, or remediation provider was modified.

### Findings

1. The private Cloud Run acceptance harness uses one Prometheus `job_name` in two security-sensitive syntactic contexts: generated Prometheus YAML and an exact PromQL label selector.
2. `run_acceptance(..., job_name=...)` previously accepted arbitrary strings. A quote/newline or selector-shaped value could make the generated config malformed or alter the query selector, weakening the meaning of the `up -> down -> up` proof.
3. The harness already rejects ambiguous Prometheus result sets, so validating the identity before building YAML/PromQL is the missing complement: the proof should have exactly one syntactically unambiguous target identity from the start.

### Exact changes made

#### 1. Hardened Prometheus acceptance job identity

Commit: `e5f9b8bcbba124b41febe6123f4c17e8c6ce9215`

`runtime/cloud_run_metrics_acceptance.py` now:
- defines `MAX_JOB_NAME_LENGTH = 128`;
- adds `normalize_job_name()` with a deliberately narrow `A-Za-z0-9_.:-` alphabet and an alphanumeric first character;
- rejects empty, boundary-whitespace, overlong, newline/space/quote, and selector-shaped job names;
- validates `job_name` at the very start of `run_acceptance()`, before target/network checks and before Docker;
- revalidates at the YAML and PromQL construction boundaries as defense in depth;
- serializes the validated YAML job name as a JSON string, which is also a valid YAML scalar.

#### 2. Added focused regression coverage

Commit: `7c84133f0e540564e62ffea51cb0c8e437c28638`

`runtime/tests/test_cloud_run_metrics_acceptance.py` now verifies:
- valid production-style job names and the 128-character boundary are accepted;
- blank, whitespace-padded, whitespace-containing, newline-containing, quote/PromQL-injection-shaped, invalid-leading-character, and overlong names are rejected;
- an invalid job name fails before unauthenticated Cloud Run probing and before Docker preflight;
- generated Prometheus configuration uses the validated quoted job identity;
- all pre-existing up/down/up, ambiguity, credential-redaction, Docker isolation, upstream recheck-order, and CLI-sanitization tests remain represented.

### Checks / results

- Authenticated GitHub inspection and all three repository writes succeeded.
- A fresh executable checkout was attempted with `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git`; the runner again failed with `Could not resolve host: github.com` before repository tests could execute.
- No GitHub Actions workflow was triggered or rerun as a workaround.
- Because the runner cannot obtain an executable checkout, `python -m unittest runtime.tests.test_cloud_run_metrics_acceptance -v` has not yet been executed against the committed tree. There is no new repository-suite green claim.

### Decisions

1. Treat the Prometheus job name as part of the acceptance proof's security/correctness contract, not as arbitrary presentation text.
2. Prefer a narrow allowlist over PromQL escaping because StageGuard controls the reference acceptance identity and does not need arbitrary Unicode/job labels for this proof.
3. Fail before any Cloud Run or Docker interaction when the identity is invalid, preserving the harness's non-destructive behavior.
4. Keep the existing exact-one-result Prometheus requirement; job-name validation narrows construction, while exact-one-result validation protects runtime observation.
5. Continue avoiding noisy GitHub Actions solely to work around the transient runner DNS failure.

### Blockers / unknowns

- `runtime.tests.test_cloud_run_metrics_acceptance` needs execution from an actual checkout after this change.
- `runtime.tests.test_onboarding`, `runtime.tests.test_telemetry`, `runtime.tests.test_cloudrun_entrypoint`, and `runtime.tests.test_deploy_cloud_run_script` still need a current repository run.
- `runtime.tests.test_mcp_smoke_timeout`, `runtime.tests.test_mcp_smoke_surface`, and `runtime.tests.test_observability_image_pins` still need an actual repository run.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required before calling that dependency baseline production-ready.
- The strengthened Cloud Run bridge six-module set still needs an executable run.
- The execution-reconciliation/operator/Playwright safety set still needs a current run.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**When executable checkout is available, run `python -m unittest runtime.tests.test_cloud_run_metrics_acceptance runtime.tests.test_onboarding runtime.tests.test_telemetry runtime.tests.test_cloudrun_entrypoint runtime.tests.test_deploy_cloud_run_script -v` first. If clean, run the MCP timeout/surface/image-pin regressions and the live pinned Grafana MCP 1.4.1 smoke; then proceed to the private `ADC -> Cloud Run /metrics -> authenticated bridge -> Prometheus up: 1 -> 0 -> 1` acceptance.**
