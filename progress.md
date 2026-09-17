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
- Consolidated validation resolves only direct non-symlink files under `runtime/tests`, fails closed on empty gates, is non-interactive and timeout-bounded, scrubs live credentials/proxies/Python injection controls, isolates Google ADC/gcloud homes and metadata identity, validates durable state and evidence/diagnosis before operator mutation gates, explicitly validates remediation and runtime-observability contracts, executes overlapping selections once under their earliest owner, classifies subprocess launch failures as validation failures, and can audit/fail closed on safe runtime tests that are not owned by any production gate.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-18 — evidence/diagnosis and observability validation ownership

### Inspected at start

Read `progress.md` completely first, then inspected the consolidated validator and the repository's recursive runtime/test inventory. The ownership audit added previously was useful immediately: several production-critical contracts were visibly outside explicit production gates, including deterministic telemetry/log evidence, investigation/briefing, Grafana runtime observability, recovery observability, and watchdog acceptance contracts.

### Changes / actions

- Added an `evidence and diagnosis` gate covering telemetry, log activation/evidence, base and correlated investigation, briefing runtime, and Gemini commander contracts.
- Added a `runtime observability` gate covering Grafana runtime observability, recovery observability, watchdog contracts, and observability image-pin safety.
- Expanded the validation-harness gate to own `test_validation_*.py`, so validator self-contracts cannot themselves become unowned as new safety gates are added.
- Added `test_validation_evidence_observability.py`, pinning minimum evidence/observability coverage and ordering: evidence must precede the operator mutation boundary; observability must precede execution safety.
- Preserved existing credential isolation, timeout, safe-file resolution, overlap de-duplication, and no-live-resource behavior.
- No credentials were read or supplied. No Docker, cloud resources, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Validator expansion committed as `3cb54102fff7d9fcab7bca2064e1b6c868caff1f`.
- Evidence/observability validation contract committed as `16e08a91b2c309a1bb92914515098da2014418a3`.
- Repository-tree inspection confirms every explicitly required contract exists on the default branch and the new patterns remain scoped to direct safe test files.
- This connector environment still does not expose an executable checkout, so no new green-test claim is made and CI was intentionally not triggered as a substitute.

### Decisions

1. Treat evidence acquisition/diagnosis as a production safety boundary, not merely feature coverage, because approval authority is downstream of those results.
2. Treat Grafana/watchdog observability as production validation because Grafana is StageGuard's indispensable runtime evidence plane and recovery claims depend on observable fresh telemetry.
3. Own validator contract tests generically under the earliest harness gate; later domain gates may select the same files, but execution-plan de-duplication prevents duplicate runs.
4. Do not indiscriminately absorb deployment/GCP acceptance tests into the dependency-light validator; they need deliberate classification because some are environment-oriented rather than local safety contracts.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Remaining unowned tests should now be materially smaller but still need classification, especially Cloud Run deployment/metrics, onboarding/readiness/UI, retention, and GCS acceptance families.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

In an executable checkout, run `python scripts/run_stageguard_validation.py --list` and then `python scripts/run_stageguard_validation.py --keep-going`; classify the remaining unowned inventory into local production contracts versus environment/acceptance tests, with operator readiness/UI and Cloud Run metrics boundaries the next highest-value candidates for explicit gates.
