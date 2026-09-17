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
- Consolidated validation resolves only direct non-symlink files under `runtime/tests`, fails closed on empty gates, is non-interactive and timeout-bounded, scrubs live credentials/proxies/Python injection controls, isolates Google ADC/gcloud homes and metadata identity, validates durable checkpoint/integrity contracts before operator mutation gates, explicitly validates remediation provider/transport/result contracts, executes overlapping selections once under their earliest owner, and classifies subprocess launch failures as validation failures.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-17 — remediation adapter validation ownership

### Inspected at start

Read `progress.md` completely first, then inspected the complete repository tree, consolidated validation runner, its existing harness regression, and the remediation/execution test inventory. The validator covered broad `test_*execution*.py` contracts but omitted several mutation-capable tests whose names are remediation/HTTP/provider-oriented rather than execution-oriented. I also found `test_local_execution_uncertainty_barrier.py` was not selected by the execution glob, and the previously added durable-state validator self-test was not itself selected by the consolidated runner.

### Changes / actions

- Added an explicit `remediation adapter boundary` gate before audit/execution/MCP gates.
- It covers the local remediation contract, reference receiver, result-boundary validation, production remediation adapter, HTTP transport and TLS integration, HTTP reconciliation/audit sequence, subprocess crash/ambiguity reconciliation, and production reconciliation bootstrap.
- Added `test_validation_remediation_boundary.py` to pin minimum provider/receiver/transport/result coverage and ordering.
- Added `test_local_execution_uncertainty_barrier.py` explicitly to the execution safety gate so the no-replay ambiguity invariant is not omitted merely because its filename lacks the generic execution glob shape.
- Added `test_validation_durable_state_integrity.py` explicitly to its durable-state gate so that earlier self-test now actually runs in consolidated validation.
- Preserved the existing validation-harness gate's exact ownership contract to avoid invalidating its established regression assertion.
- No credentials were read or supplied. No Docker, cloud resources, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Remediation gate implementation committed through `b480fe66a4acce82e1e1a6d1cd29ca9fa7739d9d` and finalized as `34bf0c0fa69e3c7b618408f2bc17c221edebddfb`.
- Remediation boundary contract added and corrected through `6acd96591416fbedb2cc7c8e226741120f043f7d`, `2d733825a0c0bf80c5e5ded5346a3dd0c68f7aca`, and `babcdd357d1c0132459ebf66b354c94ab7a29e4d`.
- Static repository-tree inspection confirms all minimum remediation contract files selected by the new gate exist.
- This connector environment does not expose an executable checkout, so no new green-test claim is made and GitHub Actions was intentionally not triggered as a substitute.

### Decisions

1. Treat remediation adapters as their own production safety boundary because they carry infrastructure-write authority independently of the incident state machine.
2. Do not rely on filename `execution` as a proxy for mutation safety coverage; explicitly own provider, transport, receiver, result, and reconciliation contracts.
3. Keep live remediation and live Grafana outside the dependency-light local validator; those remain explicit acceptance steps with credentials/environment.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

In an executable checkout, run `python scripts/run_stageguard_validation.py --list` followed by `python scripts/run_stageguard_validation.py --keep-going`; fix any remediation-boundary or durable-state failures before attempting the pinned Grafana MCP 1.4.1 live read-only smoke.
