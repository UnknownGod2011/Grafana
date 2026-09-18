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
- Consolidated validation resolves only direct non-symlink files under `runtime/tests`, fails closed on empty gates, is non-interactive and timeout-bounded, scrubs live credentials/proxies/Python injection controls, isolates Google ADC/gcloud homes and metadata identity, validates durable state, fake-cloud durability/restart behavior, fake execution/reconciliation CAS concurrency, retention safety, evidence/diagnosis, operator readiness/UI, remediation, deterministic Cloud Run deployment and GCP deployment readiness, cloud runtime metrics bridging, and runtime-observability contracts, executes overlapping selections once under their earliest owner, classifies subprocess launch failures as validation failures, and can audit/fail closed on safe runtime tests that are not owned by any production gate.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-18 — fake execution concurrency validation audit

### Inspected at start

Read `progress.md` completely first. Inspected the repository metadata/tree, consolidated validation runner, `test_execution_gcs_multiprocess_cas.py`, and `test_execution_reconciliation_gcs_multiprocess_cas.py`. Both GCS-named execution tests construct `GoogleCloudStorageCheckpointStore` only with the process-safe `SharedBucket` fake imported from `test_gcs_multiprocess_cas`; neither creates an authenticated Google Cloud client. Their remediation providers are local test doubles and their Grafana/Prometheus evidence sources are deterministic in-process fakes.

### Changes / actions

- Added an exact-filename `execution concurrency simulation` production-validation gate for `test_execution_gcs_multiprocess_cas.py` and `test_execution_reconciliation_gcs_multiprocess_cas.py`.
- Positioned the explicit gate before the broad `execution safety` gate. The existing de-duplication contract therefore executes these two files under the explicit fake-concurrency owner and reports them as already covered when the broad wildcard is evaluated.
- Added `runtime/tests/test_validation_execution_concurrency.py` to pin exact ownership, reject wildcard expansion in this gate, assert earliest-owner execution semantics, and preserve ordering after durability/remediation boundaries and before general execution safety.
- Kept the broad execution-safety family for the remaining execution contracts; this change specifically removes ambiguity about the two GCS-named multiprocess tests without weakening existing coverage.
- No credentials, Google Cloud resources, Grafana instances, Docker, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Static inspection proves both admitted tests use local multiprocessing state (`Manager` dictionaries/lists, locks, barriers, queues/events) and the `SharedBucket` fake rather than authenticated GCS.
- Static inspection also confirms remediation is represented by `SharedCountingRemediation` / `ReconciliationOnlyRemediation`; reconciliation explicitly asserts that remediation execution must never occur.
- Validation-runner update committed as `f9ed3dbc5bb8b67b992418600462a2a74cdae0c6`.
- Ownership/order regression committed as `4308cd61924b1d94b84442712639debaf54efb8e`.
- The connector environment does not expose an executable checkout, so no new green-test claim is made and CI was intentionally not triggered as a substitute.

### Decisions

1. Keep these multiprocess contracts in dependency-light production validation because all storage/provider/evidence dependencies are local fakes despite the GCS-oriented class under test.
2. Give them an exact explicit owner rather than relying solely on `test_*execution*.py`; this makes their fake-only security classification reviewable and prevents a future similarly named live test from being mistaken for the audited pair.
3. Preserve the broad execution gate for other execution tests and rely on deterministic earliest-owner de-duplication for the audited pair.
4. Do not classify `scripts/gcs_checkpoint_race_acceptance.py` as dependency-light without a separate audit; it remains outside this gate.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Remaining unowned tests need classification, notably simulator and live Gemini acceptance families.
- The rest of the broad `test_*execution*.py` selection still merits a credential/network-construction audit; only the two GCS-named multiprocess contracts were proven fake-only in this run.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Audit every remaining file selected by the broad `test_*execution*.py` production-validation pattern for network/client construction and mutation side effects, then replace broad ownership with explicit safety-classified groups where that materially reduces the risk of future live tests silently entering dependency-light validation.
