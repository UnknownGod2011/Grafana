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
- Production remediation accepts only canonical operation IDs, canonical bounded target identities at configuration/runtime boundaries, construction-frozen execution and reconciliation capabilities, an exact `TransportResult` execution-result type with strictly validated fields, strictly validated reconciliation states, and bounded finite policy configuration. Provider descriptor faults fail closed.
- Cloud Logging audit filters treat incident/log identifiers as bounded literals and reject raw control characters before issuing queries.
- Consolidated validation is credential-isolated, timeout-bounded, non-interactive, and tracks safe runtime-test ownership explicitly.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored changes have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-20 — Go/Rust toolchain isolation

### Inspected at start

Read `progress.md` completely first, then inspected `scripts/run_stageguard_validation.py`, `runtime/tests/test_validation_home_isolation.py`, and the top-level README/status. The validation environment already isolated credential/config homes, cloud credentials, proxies, Git configuration, TLS key logging/trust overrides, dynamic-loader controls, shell startup hooks, and Python/Node/Ruby/Perl/JVM/.NET startup controls. A remaining toolchain injection class existed for Go and Rust tooling invoked directly or indirectly by repository tests.

### Changes / actions

- Added `GOENV`, `GOFLAGS`, `GOTOOLCHAIN`, and `GOWORK` to the validation denylist so a caller cannot redirect Go environment/workspace/toolchain behavior inside validation children.
- Added `CARGO_HOME`, `RUSTC_WRAPPER`, `RUSTC_WORKSPACE_WRAPPER`, `RUSTFLAGS`, and `RUSTDOCFLAGS` so Cargo/rustc cannot inherit caller-selected config roots, executable wrappers, or compiler/doc flags.
- Added regression coverage for canonical, lowercase, and mixed-case forms of all nine controls while verifying ordinary settings survive sanitization.
- Kept filtering targeted instead of broadly deleting every `GO*`, `RUST*`, or `CARGO*` variable, minimizing accidental disruption of benign cross-platform test configuration.
- No workflow, live service, cloud resource, Docker environment, Grafana instance, or remediation target was touched.

### Checks / results

- Runner hardening committed as `66f9468794cf17e5e83e127dffa204dfbbf225d9`.
- Regression coverage committed as `50a7ff05aa5baba5cfc718b1e4f401d5aa6550f6`.
- Static inspection confirms the nine controls are matched case-insensitively by `_is_sensitive_env_name()` and removed before validation child environments are constructed.
- No green execution claim is made: this connector runner can inspect and modify repository files but does not provide an executable checkout for the Python suite.

### Decisions

1. Go workspace/env/toolchain selectors and Rust executable-wrapper/config controls belong inside the validation trust boundary because subprocess tests may invoke these toolchains even though StageGuard's core runtime is Python.
2. The sanitizer remains explicit and auditable rather than adopting broad language-prefix deletion that could break legitimate test behavior.
3. `PATH` remains preserved because tests legitimately resolve system tools; replacing it safely requires a cross-platform executable allowlist rather than an ad-hoc path.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout; current connector-authored changes remain unexecuted here.
- Historical full-suite failures/errors still need classification from an executable checkout.
- Live Gemini acceptance remains intentionally credentialed and outside this dependency-light runner.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

Run `scripts/run_stageguard_validation.py --require-full-coverage --keep-going` in the first executable checkout and fix every concrete failure without weakening credential isolation, no-replay semantics, or frozen provider capabilities; then perform the pinned Grafana MCP 1.4.1 read-only smoke when Docker/Grafana access is available.
