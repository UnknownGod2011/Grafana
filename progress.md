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

## Latest run — 2026-09-18 — ambient credential isolation hardening

### Inspected at start

Read `progress.md` completely first, then inspected `scripts/run_stageguard_validation.py`, `runtime/tests/test_stageguard_validation_runner.py`, `runtime/tests/test_validation_full_coverage.py`, and the repository tree. The validator already scrubbed StageGuard/Grafana/Gemini/Google credentials and common secret suffixes, but still inherited ambient credentials for adjacent developer/CI providers such as GitHub, AWS, Azure, OpenAI, Anthropic, and Hugging Face.

### Changes / actions

- Hardened `scripts/run_stageguard_validation.py` so dependency-light subprocesses also drop environment variables prefixed with `AWS_`, `AZURE_`, `ANTHROPIC_`, `OPENAI_`, `GITHUB_`, `GH_`, `HF_`, and `HUGGINGFACE_`.
- Expanded generic credential suffix scrubbing to `_ACCESS_KEY`, `_PRIVATE_KEY`, and `_CLIENT_SECRET` in addition to the existing token/API-key/password/secret suffixes.
- Added `runtime/tests/test_validation_ambient_credentials.py` to pin case-insensitive scrubbing of adjacent-provider credentials and generic private/access/client-secret names.
- Added a non-overreach regression proving ordinary non-secret provider configuration such as `GOOGLE_CLOUD_PROJECT` remains available to deterministic tests.
- The new regression is automatically owned by the existing bounded `validation harness` selector (`test_validation_*.py`), preserving full-coverage ownership without a new wildcard family.
- No credentials were read or used; no cloud resources, Docker, Grafana instances, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Runner hardening committed as `3786006374ebfea66cda205791265fdef1a92ef1`.
- Ambient-credential regression committed as `0fc786365ab6cc16b75b4f9d8f2b021c319c8deb`.
- Static inspection confirms the new test matches the existing validation-harness ownership convention and does not require external services.
- No green execution claim is made because this connector environment still does not expose an executable checkout.

### Decisions

1. Treat ambient third-party credentials as a validation-integrity risk even when StageGuard does not currently consume that provider; dependency-light tests should not accidentally become live integrations because a developer or CI runner happens to be authenticated.
2. Keep non-secret provider configuration available rather than blanking all provider-prefixed environment variables indiscriminately.
3. Preserve the existing isolated HOME/CLOUDSDK_CONFIG and metadata endpoint protections; this change is additive defense-in-depth.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first available executable checkout and fix every concrete failure without weakening credential isolation or gate ownership; once green, resume product-facing hardening from that trustworthy baseline.
