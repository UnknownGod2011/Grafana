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
- Consolidated validation resolves only direct non-symlink files under `runtime/tests`, fails closed on empty gates, is non-interactive and timeout-bounded, scrubs live credentials/proxies/Python injection controls, isolates Google ADC/gcloud homes and metadata identity, validates durable state, fake-cloud durability/restart behavior, retention safety, evidence/diagnosis, operator readiness/UI, remediation, deterministic Cloud Run deployment and GCP deployment readiness, cloud runtime metrics bridging, and runtime-observability contracts, executes overlapping selections once under their earliest owner, classifies subprocess launch failures as validation failures, and can audit/fail closed on safe runtime tests that are not owned by any production gate.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-18 — fake-cloud durability validation

### Inspected at start

Read `progress.md` completely first. Inspected the full repository tree, consolidated validation runner, `test_gcs_checkpoint.py`, `test_gcs_multiprocess_cas.py`, and `test_fake_cloud_restart_acceptance.py`. The GCS checkpoint suites implement in-memory generation-aware bucket/blob fakes (including a process-safe fake for CAS races), while fake-cloud restart acceptance patches the production bootstrap constructors to inject fake GCS and Cloud Logging implementations. These tests do not instantiate authenticated Google Cloud clients or require live resources.

### Changes / actions

- Added an exact-filename `cloud durability simulation` production-validation gate for `test_gcs_checkpoint.py`, `test_gcs_multiprocess_cas.py`, and `test_fake_cloud_restart_acceptance.py`.
- Positioned it immediately after durable-state integrity and before operator mutation/remediation/cloud-deployment boundaries.
- Added `runtime/tests/test_validation_cloud_durability.py` to pin exact ownership, prohibit wildcard expansion, and preserve safety-critical ordering.
- Deliberately did not admit `test_execution_gcs_multiprocess_cas.py`, `test_execution_reconciliation_gcs_multiprocess_cas.py`, or `scripts/gcs_checkpoint_race_acceptance.py` through this new gate; execution-family ownership remains separate and any genuinely live GCS acceptance remains outside this fake-cloud gate.
- No credentials, cloud resources, Docker, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Validation runner update committed as `65194442150a9ba1c98587e02d03c3229ad62055`.
- Gate ownership/order regression committed as `e9be889ac8498b9c5b6eb0ea7e277d4d1c3c8957`.
- Static inspection confirms the admitted checkpoint tests use local fake buckets/blobs and the restart acceptance patches production constructors before `build_runtime` creates cloud-backed services.
- The connector environment does not expose an executable checkout, so no new green-test claim is made and CI was intentionally not triggered as a substitute.

### Decisions

1. Treat fake-cloud restart as a production durability contract because it validates the real bootstrap/service lifecycle while replacing network clients at their construction boundary.
2. Use exact filenames rather than `test_gcs*.py` or `*cloud*` wildcards so future live acceptance cannot silently enter dependency-light validation.
3. Keep multiprocess fake-storage CAS in the deterministic gate because its shared state is local multiprocessing state, not GCS.
4. Preserve separate execution-safety ownership for execution/reconciliation GCS-named tests rather than conflating state-store durability with mutation lifecycle behavior.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Remaining unowned tests need classification, notably simulator and live Gemini acceptance families.
- The execution-family wildcard should be audited to ensure every GCS-named execution test is also fake-only; if any can instantiate authenticated clients it must be excluded explicitly.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Audit the two GCS-named execution/reconciliation multiprocess tests currently selected by the broad execution-safety wildcard. Prove they are fake-only and pin them explicitly, or remove them from dependency-light validation if they can instantiate authenticated Google Cloud clients.
