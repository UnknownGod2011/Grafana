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

## Latest run — 2026-09-19 — canonical remediation operation identity

### Inspected at start

Read `progress.md` completely first, then inspected the consolidated validation runner, repository runtime inventory, `README.md`, `runtime/production_remediation.py`, and `runtime/tests/test_production_remediation.py`. The production remediation boundary validated only the `sg-` prefix and total length of operation IDs, so arbitrary non-hex/control characters of the same length could pass the adapter's identity check before a provider write or reconciliation call.

### Changes / actions

- Added one canonical operation-ID validator in `runtime/production_remediation.py`: exactly `sg-` followed by 40 lowercase hexadecimal characters.
- Reused the same validator for mutation dispatch and read-only provider reconciliation so both boundaries agree and malformed identifiers fail closed before transport/provider access.
- Added regressions covering uppercase, non-hex, wrong-prefix, slash, and newline-bearing identifiers; malformed IDs make zero remediation transport calls.
- Added a reconciliation regression proving malformed IDs return `unknown` without invoking the provider reconciliation method.
- No credentials were read or used; no cloud resources, Docker, Grafana instances, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Production boundary hardening committed as `8a2bd8b89cfd8c39678d83d4a821ffec25373f33`.
- Regression coverage committed as `a7ff660cee98f464385826fabc4aad12e3f85808`.
- Static inspection confirms canonical IDs used by existing tests (`sg-` + 40 lowercase hex characters) remain accepted and malformed IDs are rejected before transport access.
- No green execution claim is made because this connector environment does not expose an executable checkout.

### Decisions

1. Operation IDs cross a consequential provider boundary and therefore use a single canonical grammar rather than prefix/length heuristics.
2. Lowercase hex matches StageGuard's deterministic hash-derived identity and avoids multiple textual representations of the same logical identifier.
3. Mutation and reconciliation share the validator to prevent disagreement that could undermine no-replay recovery semantics.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first available executable checkout and fix every concrete failure without weakening credential isolation, operation-identity safety, or gate ownership; once green, resume product-facing hardening from that trustworthy baseline.
