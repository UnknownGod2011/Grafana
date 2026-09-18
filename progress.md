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

## Latest run — 2026-09-18 — package-manager credential isolation hardening

### Inspected at start

Read `progress.md` completely first, then inspected `scripts/run_stageguard_validation.py` and `runtime/tests/test_stageguard_validation_runner.py`. The dependency-light validator already removed provider credentials, generic secret suffixes, proxies, Python injection controls, Google/AWS metadata fallback, SSH/Git credential helpers, `.netrc`, Docker config, and kubeconfig. A remaining ambient-credential channel was authenticated package-manager/client configuration inherited through pip/npm/Yarn/curl/wget environment variables.

### Changes / actions

- Added exact, case-insensitive denial for `PIP_INDEX_URL`, `PIP_EXTRA_INDEX_URL`, `PIP_CONFIG_FILE`, `NPM_CONFIG_USERCONFIG`, `YARN_RC_FILENAME`, `CURL_HOME`, and `WGETRC`.
- Added forced `PIP_NO_INPUT=1` so an unexpected pip invocation cannot fall back to an interactive prompt.
- Added `runtime/tests/test_validation_package_manager_credentials.py` covering authenticated registry URL removal, external config-file removal, case-insensitive matching, preservation of ordinary StageGuard configuration, and forced non-interactive pip behavior.
- The new regression is automatically owned by the bounded `test_validation_*.py` validation-harness gate.
- No credentials were read or used; no cloud resources, Docker, Grafana instances, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Runner hardening committed as `6819e7fa7ac289ab8fb2a387a76e512cfb2414f1`.
- Regression committed as `bb31119344c7018b1a3eee351ba86df876a4671f`.
- Static inspection confirms the new channels are exact-name, case-insensitive matches rather than broad package-related substring matching.
- No green execution claim is made because this connector environment does not expose an executable checkout.

### Decisions

1. Dependency-light validation must not inherit authenticated package registries or client credential files; these are credential sources even when no secret-looking variable name is present.
2. The denylist remains narrow so ordinary package/runtime configuration is not removed accidentally.
3. Network access is not represented as sandboxed: loopback remains intentionally available for boundary tests, while known credential discovery paths are removed.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first available executable checkout and fix every concrete failure without weakening credential isolation or gate ownership; once green, resume product-facing hardening from that trustworthy baseline.
