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

## Latest run — 2026-09-18 — generic credential suffix isolation hardening

### Inspected at start

Read `progress.md` completely first, then inspected `scripts/run_stageguard_validation.py`, the runtime test inventory, and `runtime/tests/test_stageguard_validation_runner.py`. The dependency-light validator already removed provider-specific credential namespaces, generic token/API-key/password/secret/access-key/private-key/client-secret suffixes, Google ADC locations, proxy credentials, Python injection controls, and AWS/GCE metadata credential fallback. A remaining generic gap was environment variables conventionally named `*_AUTH_TOKEN`, `*_BEARER_TOKEN`, `*_CREDENTIAL`, or `*_CREDENTIALS` for providers not yet known to StageGuard.

### Changes / actions

- Extended generic case-insensitive credential suffix matching to `_AUTH_TOKEN`, `_BEARER_TOKEN`, `_CREDENTIAL`, and `_CREDENTIALS`.
- Added `runtime/tests/test_validation_credential_suffixes.py` to pin those classifications and verify sanitization removes those secret-bearing values.
- Added a non-overmatching regression proving configuration such as `MEDIA_CREDENTIAL_MODE` and `STAGEGUARD_REGION` survives sanitization.
- The new test is automatically owned by the intentionally bounded `test_validation_*.py` validation-harness gate.
- No credentials were read or used; no cloud resources, Docker, Grafana instances, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Runner hardening committed as `5b48c8f3865f23e6485aba773934f263c8b69d3c`.
- Regression committed as `77a813526d795b9513e53ba8832f302030516a0d`.
- Static inspection confirms matching remains suffix-bounded rather than substring-based, avoiding removal of ordinary variables merely containing the word `credential`.
- No green execution claim is made because this connector environment still does not expose an executable checkout.

### Decisions

1. Dependency-light validation should fail closed for conventional secret-bearing environment names even when a future integration/provider is not yet enumerated explicitly.
2. Generic matching remains suffix-based to reduce false positives against ordinary non-secret configuration.
3. Provider-specific prefixes remain useful defense in depth because they also remove provider profile/config variables that may indirectly resolve credentials.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first available executable checkout and fix every concrete failure without weakening credential isolation or gate ownership; once green, resume product-facing hardening from that trustworthy baseline.
