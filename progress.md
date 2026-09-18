# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, no-replay execution reconciliation, recovery-only Grafana rechecks, stdio-only Grafana MCP launchers, strict operator-API authentication/framing/protocol preflight, and a loopback reference remediation provider with idempotent writes plus read-only operation reconciliation.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; provider acceptance never counts as recovery.
- Fresh Grafana telemetry is required to verify recovery; `recovery_unverified` cannot replay remediation.
- Ambiguous remediation execution remains behind the execution-uncertainty barrier until durable reconciliation and fresh evidence resolve it.
- Operator API and reference remediation provider reject ambiguous credential/body framing before mutation.
- Cloud Logging audit filters treat incident/log identifiers as bounded literals and reject raw control characters before issuing queries.
- Consolidated validation resolves only direct non-symlink files under `runtime/tests`, fails closed on empty gates, is non-interactive and timeout-bounded, scrubs live credentials/proxies/Python injection controls, isolates Google ADC/gcloud homes and metadata identity, validates the deterministic telemetry simulator before evidence consumers, durable state, fake-cloud durability/restart behavior, fake execution/reconciliation CAS concurrency, retention safety, evidence/diagnosis, operator readiness/UI, remediation, deterministic Cloud Run deployment and GCP deployment readiness, cloud runtime metrics bridging, runtime-observability contracts, restart/recovery and crash-reconciliation safety, executes overlapping selections once under their earliest owner, classifies subprocess launch failures as validation failures, and can audit/fail closed on safe runtime tests that are not owned by any production gate. Execution-safety, telemetry-simulator, and Cloud Run metrics-bridge ownership use exact admission for sensitive additions so newly added tests cannot silently enter dependency-light validation.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-18 — restart/recovery validation classification

### Inspected at start

Read `progress.md` completely first, then inspected the consolidated validation runner and the current `runtime/tests` inventory. Focused inspection covered `test_recovery_recheck_restart.py`, `test_transition_failure_snapshot_authority.py`, and `test_subprocess_crash_recovery.py`, which were safe runtime contracts not explicitly admitted by their intended production gates.

### Changes / actions

- Added `test_recovery_recheck_restart.py` and `test_transition_failure_snapshot_authority.py` explicitly to the incident-lifecycle gate.
- Added `test_subprocess_crash_recovery.py` explicitly to execution safety. It uses local multiprocessing, temporary files, POSIX SIGKILL fault injection, fake metrics, and reconciliation-only remediation; it does not contact a provider or cloud service.
- Added `test_validation_restart_recovery_ownership.py` to pin these ownership decisions and prevent replacing them with broad restart/crash wildcards.
- No credentials, cloud resources, Docker, Grafana instances, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Manual inspection confirmed the restart recheck contract restores a local JSON checkpoint and proves recovery verification cannot replay remediation after restart.
- Manual inspection confirmed transition-failure snapshot tests use in-memory audit/remediation and an injected failing checkpoint store to prove uncommitted approval/outcome state is not published.
- Manual inspection confirmed subprocess crash recovery uses temporary local checkpoint/call-log files and a spawned child killed at controlled side-effect boundaries, then verifies reconciliation without remediation replay.
- Validation runner update committed as `f4d7d4ea1d8cbf1d8e445549403263e37ad9dc01`.
- Ownership regression committed as `6383944eafeb85b4c048ff7e99f742acc1ecbfec`.
- The connector environment does not expose an executable checkout, so no new green-test claim is made and CI was intentionally not triggered as a substitute.

### Decisions

1. Restart recovery and persistence-failure authority are production lifecycle safety contracts and belong in dependency-light validation.
2. Hard-crash reconciliation belongs in execution safety because it proves at-most-once provider dispatch across process death.
3. Admit these tests by exact filename rather than broad restart/crash selectors so future integration tests require inspection before entry.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Remaining unowned safe runtime tests need explicit classification before `--require-full-coverage` can be promoted as a release criterion.
- Live Gemini acceptance remains intentionally credentialed and should not be admitted to this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Continue the unowned-test audit, beginning with any remaining safe files not selected by `GATES`; explicitly classify dependency-light tests while creating a pinned intentional-exclusion set for genuinely credentialed/live acceptance, then make `--require-full-coverage` distinguish safe exclusions from accidental omissions.
