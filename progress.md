# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the indispensable runtime evidence plane. The working vertical slice remains: deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, restart reconciliation, and a same-origin operator cockpit.

Core invariants:
- Grafana is the evidence plane; infrastructure write credentials stay isolated from Grafana/MCP access.
- Gemini is optional/advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact evidence revision.
- Remediation success is never inferred from an action response; fresh Grafana telemetry must prove recovery.
- Authenticated checkpoints and audit integrity fail closed.

## Run log — 2026-09-10 — bounded remediation execution watchdog

### Inspected at start

Read `progress.md` completely before deciding work. Inspected the production remediation/readiness path and prior HTTP concurrency implementation:
- `runtime/anchored_execution_safety.py`
- `runtime/execution_safety.py`
- `runtime/remediation.py`
- `runtime/api.py`
- `runtime/readiness.py`
- `runtime/bootstrap.py`
- `runtime/cloudrun_entrypoint.py`
- `runtime/tests/test_anchored_execution_safety.py`

Confirmed that production execution deliberately releases the lifecycle lock across provider I/O and Grafana recovery polling, and that `/readyz` already fails closed whenever `service.checkpoint_state()` reports `execution_uncertain`. The remaining gap was that an in-flight provider call could remain `dispatching` forever with no execution-age bound.

### Exact changes made

Updated `runtime/anchored_execution_safety.py`:
1. Added `DEFAULT_MAX_REMEDIATION_EXECUTION_SECONDS = 60.0`.
2. Added injectable monotonic-clock support and a bounded `execution_max_seconds` constructor parameter.
3. Reject invalid watchdog bounds, including zero, negative, boolean, infinity, NaN, and non-numeric values.
4. Record the monotonic start time immediately before an approved remediation is marked in flight.
5. Clear the active start time on both exception and normal completion paths.
6. Added `remediation_execution_observability()` returning only fixed/provider-detail-free fields: `active`, `age_seconds`, `max_seconds`, and `deadline_exceeded`.
7. Overrode `checkpoint_state()` so an active execution whose age exceeds the configured maximum reports `execution_uncertain`.
8. Preserved `dispatching` as the execution phase while the provider call is still physically in progress; competing mutations remain blocked by the existing in-flight guard.

Because the existing API readiness implementation already forces `ready=false` when checkpoint state is `execution_uncertain`, a wedged remediation now makes `/readyz` fail closed without changing provider-side behavior or attempting an unsafe cancellation/retry.

Updated `runtime/tests/test_anchored_execution_safety.py` with deterministic coverage:
- watchdog configuration rejects non-finite/non-positive/invalid values;
- a fake monotonic clock starts execution age at zero;
- execution remains synchronized before the threshold;
- crossing the configured threshold changes checkpoint state to `execution_uncertain` while phase remains `dispatching`;
- provider invocation count remains single-dispatch semantics from existing concurrency coverage;
- after the blocked provider is released and Grafana recovery verification succeeds, execution observability resets to inactive/zero-age and checkpoint state returns to synchronized with phase `resolved`.

Commits this run:
- `c3fed1db6894dd5301f63276f18f284a724d36f3` — initial bounded execution timing state
- `5e8a9d18330e1499fedac21454e499ced390bde0` — fail checkpoint/readiness state closed for wedged execution
- `70bd0138c3c66da83496e0f7e16391bd1e74c080` — deterministic watchdog regression coverage
- `e43a3e9ad14e009d2fbb5f453ebacbe369a6f9a9` — harden watchdog bound validation
- `58ad8e3b45b7bb65ca0ececa78ab1e83fe4839ae` — cover invalid watchdog bounds

### Tests / checks / results

Validation performed in this run:
- Re-fetched and reviewed the committed production service after the writes.
- Cross-checked the watchdog with `runtime/api.py`: `_service_readiness()` already sets `ready=false` for `checkpoint_state in {"conflicted", "execution_uncertain"}`.
- Cross-checked `runtime/execution_safety.py` to preserve the existing durable uncertainty and reconciliation semantics rather than mutating `_execution_uncertain` merely because a live call is slow.
- Cross-checked the default recovery loop in `runtime/remediation.py`; the 60-second watchdog is deliberately above the built-in 25 seconds of inter-sample sleep so normal six-attempt recovery verification has headroom for provider and Grafana query latency.
- Re-fetched the new deterministic test after updates and corrected its expected validation message after finite-number hardening.

The exact committed unittest module could not be executed from a repository checkout in this automation environment because `github.com` DNS resolution still fails for `git clone`. No GitHub Actions workflow was created, triggered, or rerun merely to obtain a test signal, so no full-suite green claim is made.

No external Grafana instance, MCP server, Google Cloud project, Cloud Run service, Secret Manager secret, IAM policy, Gemini endpoint, checkpoint object, or remediation endpoint was modified.

### Decisions made

1. A slow execution does not automatically become durable execution uncertainty. While the provider call is still alive, StageGuard reports transient `execution_uncertain` through `checkpoint_state()` only for readiness gating; the existing reconciliation state machine is reserved for actual ambiguous/failed execution outcomes.
2. The watchdog never cancels, retries, or replays remediation. It only withdraws readiness and exposes bounded state, preserving single-dispatch safety.
3. Monotonic time is used rather than wall-clock time so NTP/system-clock changes cannot hide or manufacture a wedge.
4. The watchdog surface contains no provider URL, operation ID, production ID, target, query, credential, or exception text.
5. The default maximum is currently an internal production-safe default rather than a deployment/CLI setting; exposing and validating that configuration is still required.

### Current blockers / unknowns

- `runtime.tests.test_anchored_execution_safety` and the HTTP concurrency suite still need execution from a runnable checkout.
- The focused production runtime/API/readiness suite should be rerun once repository execution is available.
- Execution age/deadline are not yet exported as dedicated Prometheus gauges; only the existing checkpoint-derived `stageguard_remediation_execution_uncertain` signal changes after the deadline.
- `execution_max_seconds` is not yet wired through `bootstrap.py` / production deployment configuration.
- A hung Python provider call cannot be forcibly interrupted safely by this watchdog; readiness is withdrawn, but process-level termination/replacement remains the supervisor/platform responsibility.
- The exact Cloud Storage object Policy Troubleshooter tuple still needs one authorized disposable-project acceptance run.
- Gemini deployment doctor and real Vertex AI acceptance smoke still need authorized disposable-project credentials.

## Single best next step

**Wire `remediation_execution_observability()` into the HTTP observability contract: add fixed-cardinality Prometheus gauges for active execution, execution age, configured deadline, and deadline-exceeded state; add an explicit bounded readiness check such as `remediation_execution_deadline=ok|exceeded`; then expose/validate the watchdog duration through production bootstrap configuration and cover the API behavior with the existing blocking-remediation HTTP harness.**

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
- Active remediation now has a monotonic bounded watchdog; exceeding it withdraws readiness through `execution_uncertain` checkpoint state without replaying or cancelling the action.
- Gemini acceptance smoke defaults to zero model calls and requires explicit `--execute`.
- Standard Cloud Run deployment keeps production remediation disabled.

## Validation baseline retained

- Local onboarding doctor: 8 tests passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable run: 81/81 passed.
- Historical full suite baseline: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Live Docker rehearsal: PASS twice consecutively.
- Official Grafana MCP read-only smoke path: PASS using `grafana/mcp-grafana:1.3.0`.
- Incident flow: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.
