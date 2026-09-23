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
- JSON-RPC transport frames are also decoded strictly: duplicate object members and Python-only NaN/Infinity constants fail closed before protocol state is interpreted.
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
- Hardened MCP stdio JSON-RPC decoding so ambiguous duplicate members and non-standard numeric constants cannot alter response IDs, result/error selection, or nested tool payload interpretation.

## Latest run — 2026-09-24 — strict MCP JSON-RPC transport decoding

### Inspected at start
Read `progress.md` completely, then inspected the repository tree, pinned `docker-compose.yml`, `runtime/mcp_smoke.py`, and the MCP transport regression suite. The evidence parser itself had already been hardened against duplicate JSON members and NaN/Infinity, but the outer stdio JSON-RPC transport still used Python's permissive default `json.loads`. That left a parser-differential boundary before the hardened evidence parser: duplicate `id`, `result`, `error`, or nested members used last-value-wins semantics, and Python-only NaN/Infinity tokens were accepted.

### Exact changes made
- Updated `runtime/mcp_smoke.py` in commit `859310001cd7e8461a8ccdcd5c4f02254cdf2fe6`.
- Added `_strict_json_rpc_loads`, a transport decoder that rejects duplicate object member names at every nesting level and rejects NaN/Infinity/-Infinity before any JSON-RPC protocol state is interpreted.
- Decoder failures, including JSON syntax errors, duplicate-member/non-standard-constant `ValueError`, and pathological nesting `RecursionError`, are converted to bounded `McpError` failures rather than leaking parser-specific exceptions.
- Replaced the direct `json.loads(line)` call in `StdioClient.request` with the strict transport decoder. The existing 1 MiB frame-size ceiling remains ahead of decoding.
- Updated `runtime/tests/test_mcp_smoke_transport.py` in commit `6daac48e073e60115b3168ee2d4f8fb1b1e66cb0` with positive strict-JSON coverage plus duplicate top-level ID, duplicate nested content, and all three non-standard numeric-constant regressions.
- No credentials, cloud resources, remediation targets, unrelated repositories, or GitHub Actions workflows were touched.

### Checks / results
- GitHub accepted both implementation and regression-test commits.
- Static review confirms every stdio response frame now crosses the strict decoder before notification/response classification, request-ID comparison, error handling, or result extraction.
- This connector runtime still does not expose an executable checkout, so the focused `Grafana MCP` gate was not executed here. No runtime-green claim is made.
- Historical validation numbers above remain historical.

### Decisions
1. Apply strict JSON semantics at the transport boundary as well as inside evidence text; otherwise ambiguous JSON can affect protocol routing before evidence validation runs.
2. Reject duplicate members globally rather than only security-critical names, avoiding schema-dependent parser differentials as MCP response shapes evolve.
3. Preserve the existing frame-size bound and fail closed on decoder recursion/resource errors.
4. Do not trigger GitHub Actions solely to compensate for the connector runtime's lack of an executable checkout.

### Blockers / unknowns
- The focused MCP gate still requires one executable checkout run: `python scripts/run_stageguard_validation.py --gate "Grafana MCP" --keep-going`.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Historical full-suite failures/errors still need classification.
- JSON decoding still materializes a complete transport frame up to 1 MiB; executable memory/time profiling remains pending.

## Single best next step
In an executable checkout run `python scripts/run_stageguard_validation.py --gate "Grafana MCP" --keep-going`; if green, immediately perform the pinned Grafana `13.2.1` + official MCP `1.4.1` Docker smoke and capture a sanitized real `query_prometheus` transport fixture for permanent integration coverage.
