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
- A persisted local API PID is never sufficient authority to signal a process: shutdown must structurally verify the live command signature first and retain metadata on ambiguous or failed termination.

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
- Added bounded compose ownership preflight so stopped, unhealthy, or partially-started pre-existing StageGuard containers are not destroyed when the API is unreachable.
- Fixed `--cleanup` to independently attempt host-API and compose cleanup, verify both postconditions, and aggregate failures rather than stranding one owned component when the other cleanup leg fails.
- Added critical Grafana lifecycle alert/dashboard/runbook surfaces.
- Hardened local API startup ownership so early child exit and readiness timeout cannot leave stale PID metadata; timeout cleanup targets only the exact spawned child and escalates terminate -> bounded wait -> kill/reap.
- Hardened cross-invocation API shutdown against PID reuse and replaced substring identity authorization with structured argv validation.

## Latest run — 2026-09-21 — structured persisted-PID identity validation

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected `scripts/demo_local.py` and `runtime/tests/test_demo_local_spawn_lifecycle.py`. The previous run intentionally added two red regressions proving that the persisted-PID matcher could authorize an unrelated `bootstrap.py` path or accept required values merely because they appeared elsewhere in the command line.

### Exact changes made

- Replaced substring-based `_pid_matches_stageguard_api()` authorization with fail-closed command-line parsing using Python `shlex`.
- Require exactly one bootstrap script argument resolving to StageGuard's own `runtime/bootstrap.py`; a same-basename script elsewhere no longer authorizes termination.
- Require exact option/value relationships for `--identity-mode local` and `--port 9110`; unrelated argv tokens cannot satisfy ownership.
- Reject malformed command-line quoting, missing values, duplicate bootstrap matches, duplicate ownership options, and unverifiable command lines by returning `False` rather than weakening the guard.
- Preserve Windows path normalization/quote handling while retaining the existing bounded PowerShell command lookup fallback.
- Implementation commit: `a0f3a411506065acf3a2e17bb592dafb22d4d0d8`.
- No credentials, live Grafana instance, remediation target, cloud resource, unrelated repository, or GitHub Actions workflow was touched.

### Checks / results

- GitHub accepted the implementation update.
- Static review confirms the implementation directly addresses the two focused regressions added in the preceding run: path identity is now compared against the expected StageGuard bootstrap path and option values are paired structurally.
- This repository connector does not expose an executable checkout, so `runtime/tests/test_demo_local_spawn_lifecycle.py` was not executed and no green claim is made for connector-authored changes.

### Decisions

1. Persisted PID metadata remains only a hint; termination authority requires structural live-process identity proof.
2. Ambiguous parsing, duplicate ownership-defining arguments, or malformed quoting must fail closed.
3. Process identity remains deliberately narrower than generic Python/bootstrap matching because false refusal is safer than signalling an unrelated host process.

### Blockers / unknowns

- Focused lifecycle tests still require execution in a real checkout.
- Windows command-line quoting and path normalization require live Windows validation.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

Execute `runtime/tests/test_demo_local_spawn_lifecycle.py` on Linux and Windows and fix any platform parsing discrepancy found. Then run consolidated validation, `python scripts/demo_release.py --non-interactive --cleanup`, and the pinned Grafana MCP `1.4.1` read-only smoke. If execution remains unavailable, next harden the structured identity regressions around quoted paths, `--option=value`, duplicate options, and malformed argv before moving to another production-readiness area.
