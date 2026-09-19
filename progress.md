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
- Production remediation accepts only canonical operation IDs, canonical bounded target identities at both configuration and runtime boundaries, callable provider transports, an exact `TransportResult` execution-result type with strictly validated fields, strictly validated reconciliation states, and bounded finite policy configuration; malformed runtime identities/configuration fail closed before transport.
- Cloud Logging audit filters treat incident/log identifiers as bounded literals and reject raw control characters before issuing queries.
- Consolidated validation is credential-isolated, timeout-bounded, non-interactive, and tracks safe runtime-test ownership explicitly.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored changes have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-19 — runtime remediation target identity hardening

### Inspected at start

Read `progress.md` completely first, inspected the repository root and `runtime/tests`, then reviewed `runtime/production_remediation.py` and `runtime/tests/test_production_remediation.py`. The production adapter already validated configured allowlist identities, operation IDs, provider result types, reconciliation states, retry scheduling, and finite policy values. Runtime `production_id`/`uplink` arguments, however, were compared to trusted strings before exact runtime type/canonical-form validation.

### Changes / actions

- Hardened `recover_uplink_idempotent` so both runtime target identities must pass the same exact-string, 1-128 character, no-surrounding-whitespace/no-control-character canonical validator used at construction.
- Validation now occurs before equality comparison. This prevents a caller-controlled Python object with custom `__eq__` behavior from executing inside the production mutation boundary and prevents malformed string identities from reaching provider transport.
- Invalid runtime targets fail closed with zero provider attempts; a canonical operation ID is retained only as bounded correlation metadata, while malformed operation IDs are still replaced by the empty identity.
- Attempted to obtain an executable checkout and run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going`; the container cannot resolve `github.com`, so cloning failed before any test execution. This is an environment/network limitation, not a test result.
- No CI workflow was added or triggered deliberately; no credentials, cloud resources, Docker, Grafana instances, remediation targets, or unrelated repositories were touched.

### Checks / results

- Runtime target hardening committed as `4c03444b8c7dae62f4068df7fe11811b67deb214`.
- Static inspection confirms malformed runtime target objects are rejected before equality and before `transport.execute`.
- No green execution claim is made. The attempted executable validation was blocked at repository clone by DNS/network isolation in the runner.

### Decisions

1. Python type annotations are not a production trust boundary; runtime mutation inputs must be validated before invoking comparison or provider behavior.
2. The configured allowlist and runtime target identity use the same canonical identity grammar to avoid normalization ambiguity.
3. Invalid runtime target identity remains a target rejection rather than an operation-identity error; no mutation is attempted in either case.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout; this runner's container cannot resolve GitHub.
- A dedicated regression for hostile/non-string runtime target objects should be added to the already validation-owned `runtime/tests/test_production_remediation.py` and executed when an executable checkout is available.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Add the runtime-target hostile-object regression to the existing remediation adapter boundary suite, then run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first executable checkout and fix every concrete failure without weakening credential isolation or no-replay semantics.
