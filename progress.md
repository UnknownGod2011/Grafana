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
- Consolidated validation is credential-isolated, timeout-bounded, non-interactive, and tracks safe runtime-test ownership explicitly.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-18 — cross-platform config-root credential isolation

### Inspected at start

Read `progress.md` completely first, then inspected `scripts/run_stageguard_validation.py`, the runtime tree, and `runtime/tests/test_validation_credential_helpers.py`. The validator already replaced HOME/USERPROFILE and Cloud SDK config in an isolated temporary home, but inherited XDG and Windows application-data roots could still point credential-aware transitive tooling back at the real user's configuration directories.

### Changes / actions

- Added exact, case-insensitive denial for `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `APPDATA`, and `LOCALAPPDATA` from the inherited validation environment.
- When an isolated validation home is active, explicitly re-home XDG config/data and Windows roaming/local application-data roots beneath that temporary directory rather than merely deleting them.
- Kept `CLOUDSDK_CONFIG` anchored under the same isolated XDG-style config root.
- Extended `test_validation_credential_helpers.py` to cover inherited-root removal, case-insensitive classification, and deterministic cross-platform re-homing.
- No credentials were read or used; no cloud resources, Docker, Grafana instances, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Runner hardening committed as `b467779e3bc0ade9cd758da5626ae865efa81008`.
- Regression update committed as `37eff9156aa0f0f0d9f0f0e9ac85f53f2969b39b`.
- Static inspection confirms external config roots are removed before isolated replacements are installed.
- No green execution claim is made because this connector environment does not expose an executable checkout.

### Decisions

1. HOME isolation alone is insufficient when XDG or Windows application-data roots can independently redirect credential discovery.
2. Cross-platform config roots are re-homed, not globally disabled, so dependency-light tests that legitimately need writable user configuration still have a deterministic sandbox location.
3. The validation harness remains network-capable on loopback for HTTP boundary tests; it is credential-isolated rather than represented as a full network sandbox.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first available executable checkout and fix every concrete failure without weakening credential isolation or gate ownership; once green, resume product-facing hardening from that trustworthy baseline.
