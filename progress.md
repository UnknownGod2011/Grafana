# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, no-replay execution reconciliation, recovery-only Grafana rechecks, stdio-only Grafana MCP launchers, strict operator-API authentication/framing/protocol preflight, a loopback reference remediation provider with idempotent writes plus read-only operation reconciliation, and dedicated Grafana alert/dashboard surfaces for the authoritative composite lifecycle safety state.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; provider acceptance never counts as recovery.
- Fresh Grafana telemetry is required to verify recovery; `recovery_unverified` cannot replay remediation.
- Ambiguous remediation execution remains behind the execution-uncertainty barrier until durable reconciliation and fresh evidence resolve it.
- Operator API and reference remediation provider reject ambiguous credential/body framing before mutation.
- Production remediation accepts only canonical operation IDs, bounded canonical target identities, frozen execution/reconciliation capabilities, exact validated transport/reconciliation result types, and bounded finite policy configuration.
- Consolidated validation is credential-isolated, timeout-bounded, non-interactive, and tracks safe runtime-test ownership explicitly.
- Local acceptance never destroys pre-existing compose resources merely because the StageGuard API is unreachable.
- Unattended cleanup must independently attempt all runtime components it owns, verify the host API is unreachable and compose has zero containers, and report any partial teardown as failure.
- API startup failure may terminate/reap only the exact `Popen` child created by that startup attempt; it must clear ownership metadata before returning failure.
- A persisted local API PID is never sufficient authority to signal a process: shutdown must verify the live command signature first and retain metadata on ambiguous or failed termination.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Connector-authored changes since the last executable checkout are not treated as passing tests.

## Recent completed work

- Added unattended local acceptance with `python scripts/demo_release.py --non-interactive` and opt-in `--cleanup`.
- Made compose teardown fail closed on non-zero exit and timeout-bounded at 45 seconds.
- Added a bounded compose ownership preflight so stopped, unhealthy, or partially-started pre-existing StageGuard containers are not destroyed when the API is unreachable.
- Fixed `--cleanup` to independently attempt host-API and compose cleanup, verify both postconditions, and aggregate failures rather than stranding one owned component when the other cleanup leg fails.
- Closed inherited Git/environment isolation paths in the consolidated validator and retained explicit safe Git overrides.
- Added critical Grafana alert `stageguard-lifecycle-unsafe`, a dedicated read-only lifecycle dashboard, and `docs/runbooks/lifecycle-safety.md` linked from that dashboard.
- Hardened local API startup ownership so early child exit and readiness timeout cannot leave stale PID metadata; timeout cleanup targets only the exact spawned child and escalates terminate -> bounded wait -> kill/reap.
- Hardened the final owned-child reap edge: kill is attempted only after a bounded terminate wait, a second bounded wait is mandatory, and a child that survives both produces an explicit `DemoError` while stale PID ownership metadata is still cleared.
- Hardened cross-invocation API shutdown against PID reuse: a PID loaded from disk is signalled only after bounded command-line inspection proves the expected StageGuard local API signature.

## Latest run — 2026-09-21 — strict PID identity regression gate

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected `scripts/demo_local.py` and `runtime/tests/test_demo_local_spawn_lifecycle.py`. The persisted-PID guard introduced in the previous run is directionally correct, but `_pid_matches_stageguard_api()` currently validates independent substrings: any command containing a `bootstrap.py` basename plus the tokens `local`, `--identity-mode`, `9110`, and `--port` can satisfy it. That leaves two concrete false-authorization classes: a different script with the same basename and commands where the required flag values are present elsewhere in argv rather than paired with their flags.

### Exact changes made

- Strengthened the lifecycle regression contract so a valid persisted process identity is expected to reference StageGuard's actual `runtime/bootstrap.py` path.
- Added a regression requiring a different `/tmp/.../bootstrap.py` with otherwise matching arguments to be rejected.
- Added a regression requiring `--identity-mode local` and `--port 9110` to be real flag/value pairs rather than unrelated substring presence.
- Preserved all existing startup-reap, PID-reuse, verified-shutdown, and metadata-retention tests.
- Regression commit: `3a90ea5f96668900cddd05973cb8072190c73c40`.
- No credentials, live Grafana instance, remediation target, cloud resource, unrelated repository, or GitHub Actions workflow was touched.

### Checks / results

- GitHub accepted the focused regression update.
- Static inspection confirms both new tests describe real gaps in the current substring matcher and therefore intentionally establish a red safety gate until the matcher is replaced with structured argv validation.
- This repository connector does not expose an executable checkout, so the focused pytest suite was not executed and no green claim is made.

### Decisions

1. A persisted PID may authorize termination only when process identity is structurally proven; basename/substrings are insufficient.
2. The eventual implementation should parse command arguments and verify the exact StageGuard bootstrap path plus exact option/value pairs, while failing closed when platform command-line representation cannot be parsed safely.
3. The new regressions are preferable to weakening the ownership check for Windows convenience; platform ambiguity must remain non-destructive.

### Blockers / unknowns

- The two new identity regressions are expected to fail against the current substring matcher until implementation is hardened.
- The connector can update repository files but cannot execute the checkout, so focused pytest and consolidated validation remain unexecuted here.
- Windows process-command quoting requires live validation after structured argv parsing is implemented.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

Replace `_pid_matches_stageguard_api()` substring matching with fail-closed structured argv validation: require the resolved StageGuard `runtime/bootstrap.py` path and exact `--identity-mode local` / `--port 9110` option-value pairs, then execute `runtime/tests/test_demo_local_spawn_lifecycle.py`. After that, run consolidated validation, `python scripts/demo_release.py --non-interactive --cleanup`, and the pinned Grafana MCP `1.4.1` read-only smoke.
