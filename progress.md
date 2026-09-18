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
- Consolidated validation resolves only direct non-symlink files under `runtime/tests`, fails closed on empty gates, is non-interactive and timeout-bounded, scrubs live credentials/proxies/Python injection controls, isolates Google ADC/gcloud homes and metadata identity, validates durable state, fake-cloud durability/restart behavior, fake execution/reconciliation CAS concurrency, retention safety, evidence/diagnosis, operator readiness/UI, remediation, deterministic Cloud Run deployment and GCP deployment readiness, cloud runtime metrics bridging, and runtime-observability contracts, executes overlapping selections once under their earliest owner, classifies subprocess launch failures as validation failures, and can audit/fail closed on safe runtime tests that are not owned by any production gate. Execution-safety ownership is exact-filename based so a newly added execution-named test cannot silently enter dependency-light validation.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-18 — exact execution-safety ownership hardening

### Inspected at start

Read `progress.md` completely first. Inspected the repository tree and consolidated validation runner. Enumerated the current execution-named tests. The general `execution safety` gate still used `test_*execution*.py`, which meant a future test with live network/cloud/remediation behavior could become executable in the dependency-light production validator solely because of its filename.

### Changes / actions

- Replaced the broad `test_*execution*.py` ownership pattern with the exact current set of general execution-safety contracts.
- Preserved the separately audited GCS multiprocess pair under the earlier `execution concurrency simulation` gate.
- Preserved `test_api_execution_watchdog.py` under `operator concurrency` and validation contracts under the validation-harness owner.
- Added `runtime/tests/test_validation_execution_safety_ownership.py` to assert the general execution gate contains no glob metacharacters, every current execution-named test has an intentional explicit execution owner, and the GCS multiprocess pair remains earliest-owned by the simulation gate.
- This is fail-visible by design: adding a new execution test now leaves it unowned (and visible via `--list`, fatal with `--require-full-coverage`) until a maintainer classifies it instead of silently executing it.
- No credentials, Google Cloud resources, Grafana instances, Docker, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Repository tree enumeration identified the complete current execution-named family and was used to construct exact ownership.
- Validation-runner hardening committed as `a9d85b6cb390b055c97e043991c03ca0bc8c0f46`.
- Ownership regression committed as `80849a61cc9e19c37245768ca3c2c031a1db4030`.
- The connector environment does not expose an executable checkout, so no new green-test claim is made and CI was intentionally not triggered as a substitute.

### Decisions

1. Production validation must not use a filename wildcard at the mutation/execution safety boundary because future test naming is not a security classification.
2. Existing execution contracts remain selected, but future additions require deliberate ownership review.
3. Keep the two GCS multiprocess contracts under their previously audited fake-concurrency owner rather than duplicating them in the general execution gate.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Remaining unowned tests need classification, notably `test_simulator.py`, live Gemini acceptance, and several metrics-bridge hardening tests.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Classify the currently unowned dependency-light tests, starting with the Cloud Run metrics-bridge audience/bounds/inbound-auth/redirect/sentinel contracts, and explicitly add the safe deterministic ones to the `cloud runtime metrics bridge` gate without broad wildcards.
