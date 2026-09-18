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

## Latest run — 2026-09-18 — ambient credential-helper isolation hardening

### Inspected at start

Read `progress.md` completely first, then inspected `scripts/run_stageguard_validation.py` and `runtime/tests/test_stageguard_validation_runner.py`. The validator already stripped provider credential namespaces, generic secret suffixes, proxies, Python injection controls, Google ADC paths, and AWS/GCE metadata fallback. A remaining escape hatch was inherited credential/config helper channels such as SSH agent sockets, Git/SSH askpass helpers, `.netrc`, Docker config, and kubeconfig.

### Changes / actions

- Added `SSH_AUTH_SOCK`, `SSH_AGENT_PID`, `GIT_ASKPASS`, `SSH_ASKPASS`, `GIT_SSH`, `GIT_SSH_COMMAND`, `NETRC`, `DOCKER_CONFIG`, and `KUBECONFIG` to the exact sensitive-environment denylist.
- Added `GIT_TERMINAL_PROMPT=0` as a forced validation override so a transitive Git invocation cannot fall back to an interactive credential prompt.
- Added `runtime/tests/test_validation_credential_helpers.py` covering helper/config removal, case-insensitive classification, preservation of ordinary configuration, and the forced non-interactive Git setting.
- The new regression is automatically owned by the intentionally bounded `test_validation_*.py` validation-harness gate.
- No credentials were read or used; no cloud resources, Docker, Grafana instances, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Runner hardening committed as `b040e6a7b97e40b4dfe872e3194cf9e35ba1e3ca`.
- Regression committed as `5aac59aaffb1c86a7568b976d38c097431e77807`.
- Static inspection confirms the added channels are exact-name, case-insensitive matches and therefore do not broadly remove unrelated variables.
- No green execution claim is made because this connector environment still does not expose an executable checkout.

### Decisions

1. Dependency-light validation must not inherit credential agents or external client configuration merely because no literal secret exists in the environment.
2. Loopback networking remains available because several dependency-light HTTP boundary tests require local servers; credential discovery is blocked without pretending the runner is a network sandbox.
3. Git terminal prompting is forced off independently of inherited values to preserve non-interactive behavior.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first available executable checkout and fix every concrete failure without weakening credential isolation or gate ownership; once green, resume product-facing hardening from that trustworthy baseline.
