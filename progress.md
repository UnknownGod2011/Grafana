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
- Consolidated validation resolves only direct non-symlink files under `runtime/tests`, fails closed on empty gates, is non-interactive and timeout-bounded, scrubs live credentials/proxies/Python injection controls, isolates Google ADC/gcloud homes and metadata identity, validates durable state, evidence/diagnosis, operator readiness/UI, remediation, cloud runtime metrics bridging, and runtime-observability contracts, executes overlapping selections once under their earliest owner, classifies subprocess launch failures as validation failures, and can audit/fail closed on safe runtime tests that are not owned by any production gate.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-18 — Cloud Run metrics bridge validation ownership

### Inspected at start

Read `progress.md` completely first, then inspected the consolidated validator, runtime tree, `test_cloud_run_metrics_bridge.py`, and `test_cloud_run_metrics_acceptance.py`. The bridge suite is deterministic and exercises HTTPS-origin/audience restrictions, bounded timeouts, authenticated request construction, StageGuard metric sentinel validation, loopback binding, readiness/liveness, and failure redaction. The acceptance suite uses mocks/fakes for its unit contracts, including unauthorized-upstream semantics, Prometheus selector safety, local-only scrape configuration, binary/unique `up` samples, Docker command hardening, up/down/up sequencing, and CLI error redaction; its tests do not themselves invoke a live Cloud Run service or Docker daemon.

### Changes / actions

- Added a `cloud runtime metrics bridge` production-validation gate owning `test_cloud_run_metrics_bridge.py` and `test_cloud_run_metrics_acceptance.py`.
- Positioned it before `runtime observability`, making authenticated metrics transport and acceptance semantics prerequisites for observability contracts.
- Added `test_validation_cloud_runtime_metrics.py` to pin minimum ownership and ordering and ensure the contract remains owned by the validation harness.
- Kept actual credentialed/private Cloud Run and Docker live rehearsal outside the dependency-light runner; only deterministic unit contracts were added.
- No credentials were read or supplied. No Docker, cloud resources, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Validator gate change committed as `be3d5ef03357b1841173409b77fbf022297ea225`.
- Cloud metrics validation contract committed as `c5dadd5e8c11d123fa6b08fcc6dfdec608ef23f4`.
- Repository inspection confirms both selected test files exist and their unit contracts use injected/mocked upstream, Docker, and Prometheus behavior rather than requiring live infrastructure.
- This connector environment still does not expose an executable checkout, so no new green-test claim is made and CI was intentionally not triggered as a substitute.

### Decisions

1. Treat the authenticated Cloud Run metrics bridge as a production safety boundary because Grafana runtime observability depends on trustworthy, bounded, non-leaking metrics transport.
2. Include the acceptance module's deterministic unit contracts despite its name; live acceptance remains an explicit separate operational action.
3. Use exact filenames rather than a broad `test_cloud_run_metrics*.py` glob so future credentialed/live tests cannot silently enter the local validator.
4. Preserve the existing credential-isolated validation environment even though these selected tests use fakes/mocks.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Remaining unowned tests still need classification, especially Cloud Run deployment, retention, GCS/cloud-audit, fake-cloud restart, and live Gemini acceptance families.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

In an executable checkout, run `python scripts/run_stageguard_validation.py --list` and `python scripts/run_stageguard_validation.py --keep-going`; then classify the remaining Cloud Run deployment/entrypoint tests and add only deterministic container/runtime configuration contracts to production validation while keeping credentialed deployment acceptance separate.
