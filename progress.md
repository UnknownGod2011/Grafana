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
- Production remediation accepts only canonical operation IDs, bounded canonical target identities, frozen execution/reconciliation capabilities, exact validated transport/reconciliation result types, and bounded finite policy configuration.
- Consolidated validation is credential-isolated, timeout-bounded, non-interactive, and tracks safe runtime-test ownership explicitly.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Connector-authored changes since the last executable checkout are not treated as passing tests.

## Latest run — 2026-09-20 — non-interactive local acceptance path implemented

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected the consolidated validation runner, repository test inventory, Docker Compose stack, README, scripts inventory, and `scripts/demo_release.py`. Confirmed that the local stack already pins `grafana/mcp-grafana:1.4.1` and that the release rehearsal proves healthy Prometheus evidence, starts the real local stack/MCP smoke through `demo_local.up`, injects the deterministic fault, and waits for fault evidence. The remaining orchestration problem was that the rehearsal always called `input()`, so the strongest local Docker/Grafana/MCP acceptance path could not run unattended from a terminal, development agent, or local pre-release script without adding GitHub Actions usage.

### Exact changes made

- Added `--non-interactive` to `scripts/demo_release.py`.
- Non-interactive mode skips only the human recording/operator pause; it does not skip stack recreation, startup, the Grafana MCP smoke performed by local startup, healthy baseline evidence gates, deterministic fault injection, or post-fault Prometheus evidence gates.
- Preserved the existing interactive behavior as the default.
- Reworded recording-specific terminal output so the same command is meaningful as a general local acceptance rehearsal.
- Added `runtime/tests/test_validation_demo_release_noninteractive.py` with regression coverage proving non-interactive mode never reads stdin, interactive mode still pauses, and the non-interactive main path runs baseline gates before one deterministic fault injection and then fault gates.
- Named the regression under the existing `test_validation_*.py` ownership pattern so `--require-full-coverage` does not introduce an unowned test.
- Removed the transient duplicate test filename created before assigning it to the validation-harness gate.
- Implementation commit: `e31a4ee60eceb60aba15dbf160cde0d2685d566f`.
- Validation-owned regression commit: `4ac418c263fc7c7b60121c678f2c5758249d6359` (duplicate cleanup: `8cb7cbed41423eb73f575f64c39aee1693b40e83`).
- No credentials, live Grafana instance, remediation target, cloud resource, or GitHub Actions workflow was touched. Repository Actions history remains empty, so this work adds no CI noise/storage consumption.

### Checks / results

- Static repository inspection and edits completed successfully.
- The connector does not expose an executable checkout, so the new unit regression and local Docker acceptance command were not executed; no new green-suite or MCP-1.4.1-live-smoke claim is made.
- The new regression is owned by the existing validation-harness gate through `test_validation_*.py`.

### Decisions

1. The live local acceptance path should be automatable without requiring GitHub Actions; developers and coding agents can now run `python scripts/demo_release.py --non-interactive` directly on a Docker-capable checkout.
2. Non-interactive acceptance must not weaken evidence gates. It removes only the human pause between verified healthy baseline and deterministic fault injection.
3. Interactive mode remains the default because it is useful for operator demonstrations and manual inspection.
4. Future hardening should focus on concrete executable failures and product/runtime behavior rather than further speculative environment-variable enumeration.

### Blockers / unknowns

- This repository connector can inspect/update text but cannot execute the test suite or Docker stack.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside the dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.

## Single best next step

In the first executable Docker-capable checkout, run `python scripts/run_stageguard_validation.py --require-full-coverage --keep-going`; fix every concrete failure it exposes, then run `python scripts/demo_release.py --non-interactive` to exercise the pinned Grafana MCP 1.4.1 local evidence path without manual stdin and record the exact results here.
