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
- Prometheus sample timestamps must be finite JSON numbers; numeric-looking timestamp strings are rejected.
- Evidence traversal is limited to known MCP payload envelopes and exact JSON-like built-ins; extension subclasses are opaque.
- Structured MCP evidence work is bounded by collection cardinality and scalar sizes: transport collections, Prometheus series, samples, label maps, sample-value strings, and label strings have explicit fail-closed ceilings.
- JSON text evidence is size-gated before whole-string whitespace processing, and decoder resource-guard failures fail closed rather than escaping release acceptance.
- Standard MCP content blocks are transport envelopes. Text and embedded-resource evidence must come from their actual textual payload; image/audio/resource-link blocks cannot smuggle query evidence through extension fields.
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
- Reconciled the older focused MCP regression suite with that hardened resource contract so it no longer expects forbidden `resource.data` evidence.
- Added explicit fail-closed collection/work ceilings for MCP transport collections, Prometheus series, samples, metric labels, and expected-label maps.
- Added explicit scalar-size ceilings for numeric sample strings and metric/expected label names and values so bounded collection counts cannot still carry attacker-sized scalar work.
- Hardened JSON-text evidence decoding so the 1 MiB ceiling is checked before `strip()`, and parser `ValueError`/`RecursionError` resource guards fail closed.

## Latest run — 2026-09-23 — JSON text decoder resource hardening

### Inspected at start
Read `progress.md` completely, then inspected `runtime/mcp_prometheus_evidence.py` and `runtime/tests/test_mcp_evidence_work_limits.py`. The parser already imposed a 1 MiB JSON-text ceiling, but `_decode_json_text` called `value.strip()` before checking that ceiling. An oversized upstream text payload therefore still incurred a full-string scan/allocation before rejection. I also found that `json.loads` was only catching `JSONDecodeError`; CPython resource guards such as the integer digit limit can raise `ValueError`, and pathological nesting can raise `RecursionError`, allowing hostile but size-bounded text to escape the evidence boundary as an exception.

### Exact changes made
- Updated `runtime/mcp_prometheus_evidence.py` in commit `4c18da2bbf6b78a62a7c040cf38af6cf60803aa2`.
- Reordered JSON text validation so `len(value) > MAX_JSON_TEXT_CHARS` fails before whitespace stripping or JSON parsing.
- Extended decoder failure handling to `ValueError` and `RecursionError` in addition to `JSONDecodeError`, preserving fail-closed release semantics for interpreter parser resource guards.
- Extended `runtime/tests/test_mcp_evidence_work_limits.py` in commit `287301c14bb7a5279ee51d3830df260af05dcea7` with oversized-text rejection and a 10,000-digit JSON integer regression that must return non-evidentiary rather than escape as an exception.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results
- GitHub accepted both implementation and regression-test commits.
- Static review confirms the text-size ceiling now precedes `strip()` and parsing, and known JSON parser resource-guard exceptions are converted to a non-evidentiary result.
- This connector runtime does not expose an executable repository checkout, so pytest and Docker acceptance were not run. No runtime-green claim is made for these connector-authored changes.
- Historical validation numbers above remain historical.

### Decisions
1. A resource ceiling must be enforced before operations proportional to the rejected input size; checking it after `strip()` undermines the boundary's purpose.
2. Interpreter JSON resource guards are expected hostile-input outcomes at this trust boundary and should fail closed, not crash release acceptance.
3. Keep the existing 1 MiB text ceiling for compatibility until executable profiling or a real MCP fixture justifies a tighter production value.
4. Do not trigger GitHub Actions solely to compensate for the connector runtime's lack of a checkout.

### Blockers / unknowns
- Focused MCP suites still require execution in a checkout with repository files available to Python.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification.
- JSON decoding still materializes the complete document up to 1 MiB before post-decode structural ceilings apply; executable memory/time profiling remains pending.

## Single best next step
Execute the focused MCP evidence/diagnostic suites in a real checkout and fix any regressions, then perform the pinned Grafana `13.2.1` + official MCP `1.4.1` Docker smoke and capture a sanitized real `query_prometheus` transport fixture for permanent integration coverage.
