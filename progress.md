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
- Production remediation accepts only canonical operation IDs, canonical bounded target identities, callable provider transports, an exact `TransportResult` execution-result type with strictly validated fields, strictly validated reconciliation states, and bounded finite policy configuration; malformed runtime identities/configuration fail closed before transport.
- Cloud Logging audit filters treat incident/log identifiers as bounded literals and reject raw control characters before issuing queries.
- Consolidated validation is credential-isolated, timeout-bounded, non-interactive, and tracks safe runtime-test ownership explicitly.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored changes have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-19 — exact provider result boundary

### Inspected at start

Read `progress.md` completely first, then inspected `runtime/production_remediation.py` and the repository tree. The production adapter already validated `TransportResult` field values at runtime, but used `isinstance(result, TransportResult)`. Because the provider transport is an external trust boundary, accepting arbitrary subclasses unnecessarily expands the mutation-result protocol and permits subclass-defined attribute behavior to execute during validation.

### Changes / actions

- Tightened `_valid_transport_result` from subclass acceptance to exact `TransportResult` type acceptance.
- Documented the trust-boundary rationale directly at the validator: provider-controlled subclasses must not be able to redefine field access while StageGuard validates the result of a production mutation.
- Preserved all existing strict field checks: exact booleans, bounded integer HTTP status or `None`, and rejection of contradictory accepted+retryable results.
- No CI workflow was added or triggered deliberately; no credentials, cloud resources, Docker, Grafana instances, remediation targets, or unrelated repositories were touched.

### Checks / results

- Runtime hardening committed as `8b50ec2c23b26e91e8884338d9cca0d7589dfa18`.
- Static inspection confirms provider-result subclasses now fail closed through the existing invalid-result path after exactly one provider call and cannot reach retry scheduling or accepted-action state.
- No green execution claim is made because this connector environment does not expose an executable checkout. A dedicated regression was not added blindly because the repository's validation-owned test filename could not be reliably resolved from the connector's truncated tree/code-search responses; the next executable validation pass should add/confirm that case in the existing owned policy suite rather than creating an unowned test island.

### Decisions

1. Provider execution results are a closed protocol, not an extensibility point: only StageGuard's exact immutable result carrier is accepted.
2. Duck typing/subclassing remains appropriate for the transport itself, but not for the security-sensitive mutation result crossing back into StageGuard.
3. Validation ownership is preserved rather than adding a new standalone test file that the consolidated runner may not execute.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Historical validation ownership should be used to place an exact-type regression for `TransportResult` subclasses.
- Live Gemini acceptance remains intentionally credentialed and outside this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first available executable checkout, add/confirm a validation-owned regression proving a `TransportResult` subclass fails closed after exactly one provider call, and fix every concrete failure without weakening credential isolation, no-replay remediation semantics, or validation ownership.