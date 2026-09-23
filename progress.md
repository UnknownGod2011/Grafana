# StageGuard Progress

## Current status
StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as its read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Grafana, official Grafana MCP access, bounded investigation/diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run hardening, watchdog observability, execution reconciliation, and hardened local lifecycle tooling.

## Core invariants
- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; provider acceptance never counts as recovery.
- Fresh Grafana telemetry is required to verify recovery; ambiguous execution cannot replay remediation.
- MCP release acceptance requires meaningful evidence, exact datasource UID, and a genuine Prometheus vector/matrix sample bound to expected labels on the same sampled series.
- Prometheus sample timestamps and numeric sample values must be finite, exact built-in numerics representable as float64; arbitrary-precision structured integers fail closed. Numeric-looking timestamp strings are rejected.
- Evidence traversal is limited to known MCP payload envelopes and exact JSON-like built-ins; extension subclasses are opaque.
- Structured MCP evidence work is bounded by collection cardinality and scalar sizes.
- JSON text evidence is size-gated before whole-string whitespace processing; decoder resource-guard failures, duplicate object keys, and non-standard NaN/Infinity constants fail closed.
- Standard MCP content blocks are transport envelopes; only actual textual payloads can carry JSON evidence.
- Embedded resources admit evidence only through exact-string `resource.text`; URI-less `resource.data`, blob payloads, and arbitrary resource extensions are non-evidentiary.
- Raw PromQL/evidence/sample payloads must not be emitted by normal release-smoke success output.
- Upstream MCP failure material must pass through secret-aware, bounded, display-safe diagnostics before becoming operator-visible.
- Validation claims distinguish historical executable results from connector-authored changes not yet run in a checkout.

## Retained validation baseline
- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest lifecycle/security hardening.
- Historical official Grafana MCP smoke: PASS on `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires live smoke.
- Connector-authored changes since the last executable checkout are not treated as passing tests.

## Recent completed work
- Hardened lifecycle startup/cleanup, Docker timeouts, teardown verification, loopback publishing, and MCP container privileges/resources.
- Pinned Grafana `13.2.1` and official Grafana MCP `1.4.1`; release smoke verifies read-only tools and exact datasource UID.
- Added bounded semantic Prometheus evidence parsing with expected-label binding and strict sample-pair semantics.
- Added secret-aware MCP diagnostics with hostile-object protection, collision preservation, display-control escaping, credential redaction, strict output ceilings, exact truncation accounting, and metaclass-hook isolation.
- Restricted evidence traversal so warning/annotation/extension lookalikes and standard content-block `data` siblings cannot create false release acceptance.
- Hardened embedded MCP resources so only textual payloads can carry JSON evidence; blob/resource-link/extension fields cannot masquerade as telemetry.
- Removed the temporary URI-less `resource.data` compatibility path after inspecting the pinned official mcp-grafana v1.4.1 `QueryPrometheusResult` contract.
- Added explicit fail-closed collection/work and scalar-size ceilings.
- Hardened JSON-text evidence decoding so the 1 MiB ceiling precedes `strip()`, parser resource-guard failures fail closed, duplicate object member names are rejected, and Python-only NaN/Infinity constants cannot create parser-differential acceptance.
- Hardened already-structured numeric evidence so arbitrary-precision Python integers that cannot be represented by the upstream float64-oriented Prometheus model are rejected rather than bypassing JSON decoder digit limits.
- Added focused validation-gate selection so the MCP regression boundary can be executed without paying the cost of the entire production safety suite.

## Latest run — 2026-09-23 — focused executable validation path

### Inspected at start
Read `progress.md` completely, then inspected the hardened MCP evidence boundary, the runtime test inventory, `scripts/run_stageguard_validation.py`, and its validation-runner regressions. The repository already had a comprehensive isolated validation harness and a dedicated `Grafana MCP` gate, but there was no way to execute only that gate. That made the repeatedly identified next step—running the focused MCP suites—unnecessarily expensive and encouraged either ad-hoc test commands or a full validation run.

### Exact changes made
- Updated `scripts/run_stageguard_validation.py` in commit `4718190c1396ef52d03b9e489209098a48989cee`.
- Added repeatable `--gate NAME` selection using exact canonical gate names. No `--gate` preserves the existing all-gates behavior.
- Selection preserves canonical gate order and deduplicates repeated names; unknown names fail closed before any test subprocess launches.
- `--require-full-coverage` remains a global repository-coverage assertion even when execution is focused, so selecting one gate cannot hide newly unowned runtime tests.
- Added `runtime/tests/test_validation_gate_selection.py` in commit `6021bdec0616165a08db9d30ee997721573a645e` with coverage for default behavior, canonical ordering/deduplication, unknown-gate rejection, focused MCP-only execution, and global full-coverage semantics.
- The new regression file is automatically owned by the existing `validation harness` gate through its `test_validation_*.py` pattern.
- Focused MCP execution is now: `python scripts/run_stageguard_validation.py --gate "Grafana MCP" --keep-going`.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results
- GitHub accepted the runner and regression-test commits.
- Static review confirms the default path still selects `GATES` unchanged and that focused selection happens before the execution plan is built.
- This connector runtime still does not expose an executable repository checkout, so the newly simplified MCP command and its tests were not executed here. No runtime-green claim is made.
- Historical validation numbers above remain historical.

### Decisions
1. Prefer extending the existing credential-scrubbed validation harness over introducing another MCP-specific runner.
2. Gate names are exact rather than fuzzy to prevent typo-driven partial validation.
3. Focused execution must not weaken `--require-full-coverage`; coverage ownership is a repository-wide invariant.
4. Do not trigger GitHub Actions solely to compensate for the connector runtime's lack of a checkout.

### Blockers / unknowns
- The focused MCP gate still requires one executable checkout run; it is now a single explicit command rather than a full-suite requirement.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification.
- JSON decoding still materializes the complete document up to 1 MiB before post-decode structural ceilings apply; executable memory/time profiling remains pending.

## Single best next step
In an executable checkout run `python scripts/run_stageguard_validation.py --gate "Grafana MCP" --keep-going` and fix any regression it exposes; if green, immediately perform the pinned Grafana `13.2.1` + official MCP `1.4.1` Docker smoke and capture a sanitized real `query_prometheus` transport fixture for permanent integration coverage.
