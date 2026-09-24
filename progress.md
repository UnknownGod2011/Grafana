# StageGuard Progress

## Current status
StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as its read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Grafana, official Grafana MCP access, bounded investigation/diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run hardening, watchdog observability, execution reconciliation, and hardened local lifecycle tooling.

## Core invariants
- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; provider acceptance never counts as recovery.
- Fresh Grafana telemetry is required to verify recovery; ambiguous execution cannot replay remediation.
- MCP acceptance requires meaningful evidence, exact datasource UID, and a genuine Prometheus vector/matrix sample bound to expected labels on the same sampled series.
- Evidence traversal and structured work are bounded; JSON/MCP inputs reject duplicate members, non-finite numerics, invalid protocol identity, hostile container subclasses, and oversized structures.
- MCP tool discovery is bounded and every advertised tool must carry literal `readOnlyHint=true`.
- Raw PromQL/evidence/sample payloads must not be emitted by normal release-smoke success output.
- Remote Grafana credential bootstrap is explicit-opt-in and HTTPS-only; loopback HTTP remains available locally. Bootstrap targets are strict origins.
- Sanitized MCP captures replay offline through the same production tool-surface, result-envelope, datasource-identity, and Prometheus semantic validators.
- Fixture expected-label selectors are bounded to 32 entries with Prometheus-compatible names and UTF-8 byte limits.
- Fixture input is accepted only from an opened regular file; the type is checked race-safely with `fstat` before reading, and at most 1 MiB + 1 sentinel byte is consumed.
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
- Hardened JSON-text evidence and MCP JSON-RPC transport decoding, response identity, tool discovery, generic tool-result envelopes, and secret-aware diagnostics.
- Hardened Grafana Viewer-token bootstrap so remote admin credentials cannot be sent over plaintext HTTP or via non-origin/credential-bearing URLs.
- Added an offline sanitized MCP fixture replay validator using production MCP validators, with bounded selectors, byte-oriented scalar limits, strict UTF-8/JSON, and bounded byte reads.

## Latest run — 2026-09-24 — reject special fixture files

### Inspected at start
Read `progress.md` completely, then inspected `runtime/mcp_fixture_replay.py` and its focused regression suite. The principal pending executable milestone remains Grafana `13.2.1` + official MCP `1.4.1` acceptance. The replay loader's previous bounded read still opened arbitrary filesystem object types, so an unattended invocation pointed at a FIFO/device could block or consume non-file input despite the byte ceiling.

### Exact changes made
- Commit `62d554fb82bc434e8706d74065a3335bd231fe7b` adds an opened-descriptor `os.fstat()` / `stat.S_ISREG()` boundary before fixture reads.
- The check occurs after open, so pathname replacement cannot swap a previously validated regular file for a special file between validation and read.
- FIFOs, devices, sockets, and other non-regular descriptors now fail before `read()`; the existing 1 MiB + 1 sentinel byte ceiling remains unchanged.
- Commit `a62410818fa9a416cf30114ee0327996371caf5a` adds a portable FIFO regression (skipped where `os.mkfifo` is unavailable) that ensures a named pipe is rejected as a non-regular fixture.
- No Actions workflows, credentials, cloud resources, remediation targets, or unrelated repositories were touched.

### Checks / results
- GitHub accepted both implementation and regression commits.
- Static inspection confirms the descriptor type is checked before fixture bytes are consumed and that the existing bounded-read and strict JSON path remains intact.
- This connector runtime still does not expose an executable checkout, so the focused MCP gate and new regression were not executed; no new green claim is made.

### Decisions
1. Treat sanitized acceptance captures as regular-file artifacts, not arbitrary byte streams.
2. Validate the opened descriptor rather than pathname metadata to avoid a check/use race.
3. Preserve local/free operation and avoid triggering GitHub Actions solely to obtain validation in this connector runtime.

### Blockers / unknowns
- The focused MCP gate still requires an executable checkout: `python scripts/run_stageguard_validation.py --gate "Grafana MCP" --keep-going`.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Connector-authored replay changes are not yet executed.
- Historical full-suite failures/errors still need classification after the focused MCP boundary is green.

## Single best next step
Run the focused `Grafana MCP` validation gate in an executable checkout. Once green, perform the pinned Grafana `13.2.1` + official MCP `1.4.1` Docker smoke, retain only the sanitized semantic capture expected by `runtime/mcp_fixture_replay.py`, and replay it locally to lock the actual current server response shape into regression coverage.
