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
- Consolidated validation resolves only direct non-symlink files under `runtime/tests`, fails closed on empty gates, is non-interactive and timeout-bounded, scrubs live credentials/proxies/Python injection controls, isolates Google ADC/gcloud homes and metadata identity, validates durable state, evidence/diagnosis, operator readiness/UI, remediation, and runtime-observability contracts, executes overlapping selections once under their earliest owner, classifies subprocess launch failures as validation failures, and can audit/fail closed on safe runtime tests that are not owned by any production gate.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-18 — operator readiness and UI validation ownership

### Inspected at start

Read `progress.md` completely first, then inspected the consolidated validator and the runtime test inventory. The remaining unowned inventory included a coherent local operator-facing family: bootstrap, incident service, onboarding, readiness, operator console/browser behavior, preflight/doctor, and command-line contracts. These are dependency-light production contracts rather than live cloud acceptance tests.

### Changes / actions

- Added an `operator readiness and UI` validation gate before the operator API mutation boundary.
- The gate owns bootstrap and incident-service construction, onboarding/readiness checks, readiness API behavior, local short-circuit behavior, operator console/DOM/browser safety behavior, operator integrity/recovery presentation, preflight CLI, StageGuard doctor, and command-line bounds.
- Added `test_validation_operator_readiness.py` to pin minimum ownership and ordering so these contracts cannot silently fall out of consolidated production validation.
- Kept Cloud Run deployment/metrics, GCS multiprocess, Gemini live acceptance, and other credential/environment-oriented acceptance families outside this dependency-light gate pending deliberate classification.
- No credentials were read or supplied. No Docker, cloud resources, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Validator gate change committed as `ec51c6888be48be621d2105bf5575dabea1b9f13`.
- Operator-readiness validation contract committed as `7d461e0516192baa4473b63a822a496bc715b868`.
- Repository inventory confirms every explicitly required operator-readiness contract exists on the default branch; `test_validation_operator_readiness.py` is selected by the existing `test_validation_*.py` harness pattern.
- This connector environment still does not expose an executable checkout, so no new green-test claim is made and CI was intentionally not triggered as a substitute.

### Decisions

1. Treat operator readiness and UI safety as a production boundary because the console is where humans inspect evidence and authorize lifecycle actions.
2. Validate this boundary before the operator API mutation gate so construction/readiness/presentation failures surface before mutation-capable contracts.
3. Keep broad `test_operator_*.py` ownership because new operator-surface safety regressions should enter consolidated validation by default.
4. Continue separating local deterministic production contracts from tests whose purpose is live cloud acceptance.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Remaining unowned tests still need classification, especially Cloud Run deployment/metrics bridge, retention, GCS/cloud-audit, fake-cloud restart, and live Gemini acceptance families.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

In an executable checkout, run `python scripts/run_stageguard_validation.py --list` and `python scripts/run_stageguard_validation.py --keep-going`; then classify the Cloud Run metrics-bridge tests, separating deterministic authentication/audience/bounds/redirect contracts suitable for local production validation from the credentialed live acceptance test.
