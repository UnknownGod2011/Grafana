# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, no-replay execution reconciliation, recovery-only Grafana rechecks, stdio-only Grafana MCP launchers, strict operator-API authentication/framing/protocol preflight, a loopback reference remediation provider with idempotent writes plus read-only operation reconciliation, and Grafana lifecycle safety surfaces.

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
- Cleanup independently attempts all requested runtime components it owns and reports partial teardown as failure.
- API startup failure may terminate/reap only the exact `Popen` child created by that startup attempt.
- A persisted local API PID is never sufficient authority to signal a process; shutdown structurally verifies the live command signature first.
- Health reachability is not process ownership: a structurally verified unhealthy local API is still an owned process.
- Persisted PID metadata must be a strictly positive process ID before lookup or signal.
- Local stop must not report success if teardown of an owned component fails.
- Successful Compose teardown must be verified against all project containers, including stopped containers, not inferred solely from `docker compose down` returning zero or the default running-only `compose ps` view.
- Local Docker Compose subprocesses are timeout-bounded so a wedged daemon cannot indefinitely block startup, shutdown, or cleanup verification.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Connector-authored changes since the last executable checkout are not treated as passing tests.

## Recent completed work

- Added unattended local acceptance with `python scripts/demo_release.py --non-interactive` and opt-in `--cleanup`.
- Hardened unattended Compose ownership preflight/teardown and aggregate cleanup verification.
- Added critical Grafana lifecycle alert/dashboard/runbook surfaces.
- Hardened local API startup ownership so early child exit/readiness timeout cannot strand stale PID metadata; cleanup targets only the exact spawned child.
- Hardened cross-invocation API shutdown against PID reuse with structured argv validation.
- Decoupled API health from process ownership; verified unhealthy processes are still safely cleaned up.
- Rejected zero/negative persisted PIDs before process lookup/signalling.
- Implemented truthful local stop teardown: missing Docker or non-zero `docker compose down` becomes `DemoError`; `Stopped.` is emitted only after successful teardown or explicit `--keep-stack`.
- Implemented independent local stop cleanup so API failure no longer suppresses owned Compose teardown; multiple failures are aggregated.
- Implemented post-`down` all-state project-container verification before local stop can report success.
- Bounded every local Docker Compose subprocess and made teardown/verification timeout failures explicit and fail-closed.

## Latest run — 2026-09-21 — bounded local Compose lifecycle

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected `scripts/demo_local.py`, `scripts/demo_release.py`, and the focused local-stop lifecycle regression suite. Confirmed the release rehearsal already bounds Compose subprocesses, while the normal local demo path did not.

### Finding

`demo_local.py` used unbounded `subprocess.run` calls for Docker Compose. A wedged Docker daemon could therefore hang normal startup, stop, or post-teardown verification indefinitely. This undermined the otherwise fail-closed cleanup guarantees and differed from the already timeout-bounded unattended release rehearsal.

### Exact changes made

- Added `COMPOSE_COMMAND_TIMEOUT_SECONDS = 90.0` to the normal local demo path.
- Extended `_run()` with an optional timeout and made `_docker()` apply the Compose timeout to every local Compose command.
- Bounded the Docker Compose version preflight as well.
- Added controlled timeout diagnostics for Compose teardown and post-teardown verification; timeout state remains a cleanup failure and never prints false success.
- Added `subprocess.TimeoutExpired` to the top-level local CLI error boundary.
- Added regression coverage for teardown timeout, verification timeout, and `_docker()` timeout propagation.
- Implementation commit: `47862180f82f9951afe6b4ffa89c45a19dc72007`.
- Regression commit: `9721bfeabf63b6befd982d9a601b866a8476480c`.
- No credentials, cloud resources, live remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results

- GitHub accepted both source and regression updates.
- Static inspection confirms timeout handling is now present at the local Compose boundary and cleanup continues to fail closed on unknown state.
- No executable green claim is made: the connector environment does not provide a runnable checkout, so the new and accumulated lifecycle tests remain pending execution.

### Decisions

1. A wedged Docker daemon is an operational failure, not a reason for the local CLI to wait forever.
2. The normal local path now follows the same bounded-subprocess principle already used by `demo_release.py`.
3. Timeout during teardown or verification is reported as incomplete cleanup; StageGuard never infers absence of resources from an uncompleted command.
4. No CI workflow was introduced solely to execute this gate, preserving the low-noise Actions policy.

### Blockers / unknowns

- Focused lifecycle tests require execution in a real checkout, including Windows command-line parsing validation.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live unattended Docker rehearsal is required after the accumulated cleanup hardening.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

Execute the accumulated local lifecycle suites on Linux and Windows, then run consolidated validation and classify any failures before the unattended Docker cleanup rehearsal and pinned Grafana MCP `1.4.1` read-only smoke.
