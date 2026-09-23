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

## Latest run — 2026-09-23 — structured numeric representability boundary

### Inspected at start
Read `progress.md` completely, then inspected `runtime/mcp_prometheus_evidence.py` and `runtime/tests/test_mcp_evidence_work_limits.py`. JSON text already had an interpreter digit guard, but already-structured MCP objects could still inject an arbitrary-precision Python `int` as a timestamp or sample value. `_finite_timestamp` accepted every exact `int`, and `_finite_sample_value` did the same, so this path bypassed the JSON decoder's integer resource guard and admitted values not representable by the upstream float64-oriented Prometheus model.

### Exact changes made
- Updated `runtime/mcp_prometheus_evidence.py` in commit `ef349dda221fabf4c3a989249b46c0989f5d1a49`.
- Added `_finite_builtin_number`, shared by timestamp and sample validation.
- Exact built-in floats must remain finite. Exact built-in integers must be convertible to a finite float64-like Python float; `OverflowError` fails closed. Booleans and numeric subclasses remain rejected by exact-type checks.
- Numeric string sample behavior and its existing 128-character ceiling are unchanged.
- Extended `runtime/tests/test_mcp_evidence_work_limits.py` in commit `2580c3b5effb67d5a34b168548844d12be16d072` with arbitrary-precision structured timestamp and sample-value regressions plus a finite numeric positive control.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results
- GitHub accepted both implementation and regression-test commits.
- Static review confirms `float(10**10000)` raises `OverflowError`, which the new helper converts to non-evidence, while ordinary finite integer/float samples remain accepted.
- This connector runtime does not expose an executable repository checkout, so pytest and Docker acceptance were not run. No runtime-green claim is made for these connector-authored changes.
- Historical validation numbers above remain historical.

### Decisions
1. Structured MCP objects must not have a looser numeric domain than JSON-decoded evidence.
2. Numeric evidence should be representable by the upstream Prometheus model rather than merely by Python's arbitrary-precision integer type.
3. Preserve exact-type checks so hostile numeric subclasses and booleans remain opaque/non-evidentiary.
4. Do not trigger GitHub Actions solely to compensate for the connector runtime's lack of a checkout.

### Blockers / unknowns
- Focused MCP suites still require execution in a checkout with repository files available to Python.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification.
- JSON decoding still materializes the complete document up to 1 MiB before post-decode structural ceilings apply; executable memory/time profiling remains pending.

## Single best next step
Execute the focused MCP evidence/diagnostic suites in a real checkout and fix any regressions, then perform the pinned Grafana `13.2.1` + official MCP `1.4.1` Docker smoke and capture a sanitized real `query_prometheus` transport fixture for permanent integration coverage.
