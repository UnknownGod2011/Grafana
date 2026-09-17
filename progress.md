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
- Consolidated validation resolves only direct non-symlink files under `runtime/tests`, fails closed on empty gates, is non-interactive and timeout-bounded, scrubs live credentials/proxies/Python injection controls, isolates Google ADC/gcloud homes and metadata identity, validates durable checkpoint/integrity contracts before operator mutation gates, executes overlapping selections once under their earliest owner, and classifies subprocess launch failures as validation failures.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-17 — durable state validation ownership

### Inspected at start

Read `progress.md` completely first, then inspected the consolidated validator, its self-tests, the runtime test inventory, and checkpoint file-security coverage. The recommended safety runner already owned activation, API ingress/concurrency, incident lifecycle, audit/timeline, execution, and Grafana MCP contracts, but checkpoint/file-integrity persistence was not an explicit pre-mutation gate even though durable state is part of StageGuard's authority model.

### Changes / actions

- Added a `durable state integrity` gate before all operator mutation/lifecycle gates.
- The gate selects checkpoint, integrity, and file-lock contracts, giving persistence safety explicit ownership while existing overlap de-duplication prevents repeated execution of tests also selected by audit gates.
- Added `test_validation_durable_state_integrity.py`, which fails if checkpoint file-security coverage disappears, if no independent integrity contract remains, or if the durable-state gate moves behind API/concurrency/lifecycle gates.
- Updated validator documentation to explain why durable persistence must validate before operator traffic is considered safe.
- No credentials were read or supplied. No Docker, cloud resources, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Validator change committed as `2fb0405ae69d24be5a50617abf669643aa6c62f4`.
- Durable-state contract test committed as `5d26f97d6f01a705c97a34b9f705d3f0d2dae80b`.
- Static inspection confirms `test_checkpoint_file_security.py` exists and is selected by the new checkpoint glob.
- This connector environment does not expose an executable checkout, so no new green-test claim is made and GitHub Actions was intentionally not triggered as a substitute.

### Decisions

1. Treat durable checkpoint/integrity behavior as a first-class production safety boundary, not merely an incidental part of broad audit coverage.
2. Run this boundary before API mutation/lifecycle gates because approval/execution authority depends on trustworthy persisted state.
3. Keep broad patterns for checkpoint/integrity/file-lock contracts so newly added persistence regressions are automatically incorporated, with a dedicated contract test preventing silent erosion of the minimum expected boundary.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

In an executable checkout, run `python scripts/run_stageguard_validation.py --list` and `python scripts/run_stageguard_validation.py --keep-going`; fix any durable-state or other failures before the pinned Grafana MCP 1.4.1 live read-only smoke.
