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
- Consolidated validation resolves only direct non-symlink files under `runtime/tests`, fails closed on empty gates, is non-interactive and timeout-bounded, scrubs live credentials/proxies/Python injection controls, isolates Google ADC/gcloud homes and metadata identity, validates durable state, retention safety, evidence/diagnosis, operator readiness/UI, remediation, deterministic Cloud Run deployment and GCP deployment readiness, cloud runtime metrics bridging, and runtime-observability contracts, executes overlapping selections once under their earliest owner, classifies subprocess launch failures as validation failures, and can audit/fail closed on safe runtime tests that are not owned by any production gate.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-18 — GCP deployment readiness validation ownership

### Inspected at start

Read `progress.md` completely first, then inspected the repository tree, consolidated validator, GCP deploy-doctor family, and identifier tests. The doctor family contains offline subprocess validation, module-level mocked permission checks, a POSIX fake-`gcloud` full preflight, process-failure handling, serialization, and identifier validation. The fake-cloud suite shadows `gcloud` via a temporary executable and records invocations rather than consulting an installed authenticated CLI. fileciteturn6file0 The offline/permission suite either runs `--offline` or patches `_run_gcloud`, including least-privilege Secret Manager, Logging, Storage and Vertex permission contracts. fileciteturn7file0

### Changes / actions

- Added a `GCP deployment readiness` production-validation gate owning exactly `test_gcp_deploy_doctor.py`, `test_gcp_deploy_doctor_fake_gcloud.py`, `test_gcp_deploy_doctor_process_failures.py`, `test_gcp_deploy_doctor_serialization.py`, and `test_gcp_identifiers.py`.
- Positioned it after the static Cloud Run deployment contract and before the private metrics bridge: deployment syntax/configuration is validated first, then deploy-time readiness behavior, then runtime observability plumbing.
- Added `test_validation_gcp_deployment_readiness.py` to pin exact ownership and ordering and explicitly reject wildcard admission.
- Used exact filenames so a future live GCP acceptance test cannot silently enter dependency-light validation.
- No credentials were read or supplied. No real `gcloud` account/project state, cloud resources, Docker, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- GCP deployment-readiness gate committed as `de7a618b3c89e73796fe742a84f5e77b9df1b7df`.
- Validation ownership regression committed as `63c83e001863bdcea00c150438010bf7823e922d`.
- Static inspection confirms the fake-gcloud acceptance exercises region/API/bucket/image/permission readiness without real cloud access, including fail-closed unsupported-region and denied-permission cases. fileciteturn6file0
- Static inspection confirms the offline doctor validates checkpoint, Grafana, service-account, Artifact Registry, Gemini and identifier boundaries and that permission tests mock `_run_gcloud`. fileciteturn7file0
- This connector environment still does not expose an executable checkout, so no new green-test claim is made and CI was intentionally not triggered as a substitute.

### Decisions

1. Treat deploy-time readiness as distinct from static deployment contracts: both must pass before a production rollout is considered trustworthy.
2. Admit only the five currently inspected deterministic GCP doctor/identifier files; exact ownership is safer than a broad `test_gcp*.py` pattern.
3. Preserve credential isolation even for tests that emulate `gcloud`; validation must never inherit developer ADC, gcloud homes, metadata identity, or proxy credentials.
4. Keep genuinely live Cloud Run/GCS/Gemini acceptance outside this runner and require explicit operator-controlled environments for those checks.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Remaining unowned tests still need classification, especially cloud-audit/GCS, fake-cloud restart, simulator, and live Gemini acceptance families.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Classify the fake-cloud restart and cloud-audit/GCS test families next. Separate pure in-memory/fake-storage durability contracts from tests that can instantiate real Google Cloud clients, then add only the deterministic subset to consolidated production validation with exact ownership.
