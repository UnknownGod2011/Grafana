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

## Latest run — 2026-09-18 — cloud metadata credential isolation hardening

### Inspected at start

Read `progress.md` completely first, then inspected `scripts/run_stageguard_validation.py` and `runtime/tests/test_stageguard_validation_runner.py`. The dependency-light runner already isolated Google metadata/ADC paths and scrubbed AWS-prefixed ambient environment variables, but an AWS SDK imported by a future or transitive test could still attempt EC2 Instance Metadata Service credential discovery after the inherited `AWS_EC2_METADATA_DISABLED` value had been removed.

### Changes / actions

- Added an explicit `AWS_EC2_METADATA_DISABLED=true` validation-environment override after credential scrubbing.
- This keeps AWS-prefixed ambient credentials/profiles removed while making the post-scrub environment fail closed against AWS IMDS credential discovery.
- Added a regression proving an inherited `AWS_EC2_METADATA_DISABLED=false`, `AWS_PROFILE`, and `AWS_ACCESS_KEY_ID` are replaced/removed correctly while ordinary configuration survives.
- Preserved loopback networking because several dependency-light HTTP boundary tests intentionally use local servers; this change targets credential discovery rather than indiscriminately disabling sockets.
- No credentials were read or used; no cloud resources, Docker, Grafana instances, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Runner hardening committed as `6d707935c2400b908bb02c53ce80bf01151a1a20`.
- Regression committed as `0ac4a57db023419f16e8bf3ce8abaa52c652896a`.
- Static inspection confirms the override is applied after AWS-prefixed environment scrubbing, so an unsafe inherited `false` value cannot survive.
- No green execution claim is made because this connector environment still does not expose an executable checkout.

### Decisions

1. Credential isolation must cover SDK metadata fallback, not only explicit environment/file credentials.
2. Keep deterministic loopback HTTP tests functional rather than introducing a coarse network ban into the existing validator.
3. Continue treating dependency-light validation as fail-closed: future provider SDK imports should not silently acquire ambient machine identity.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first available executable checkout and fix every concrete failure without weakening credential isolation or gate ownership; once green, resume product-facing hardening from that trustworthy baseline.
