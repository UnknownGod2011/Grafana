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
- Fixture input is opened non-blocking where supported, final-component symlinks are refused where `O_NOFOLLOW` exists, the opened descriptor must be a regular file, and at most 1 MiB + 1 sentinel byte is consumed.
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
- Added an offline sanitized MCP fixture replay validator using production MCP validators, with bounded selectors, byte-oriented scalar limits, strict UTF-8/JSON, bounded reads, non-blocking special-file rejection, and no-follow protection where supported.

## Latest run — 2026-09-24 — prevent pre-validation FIFO blocking

### Inspected at start
Read `progress.md` completely, then inspected `runtime/mcp_fixture_replay.py` and `runtime/tests/test_mcp_fixture_replay.py`. The previous run correctly added an opened-descriptor regular-file check, but static inspection found that `Path.open("rb")` itself is a blocking operation. An unattended replay pointed at a FIFO with no writer could therefore hang before `fstat()` ever had a chance to reject the descriptor. The prior FIFO regression masked this because it deliberately kept a read/write FIFO descriptor open.

### Exact changes made
- Commit `fb4576706c333f888909590b21c478f6e0370582` replaces `Path.open()` with descriptor-level `os.open()`.
- Fixture open now adds `O_NONBLOCK` where available, so an unconnected FIFO cannot hang before descriptor validation.
- Fixture open also adds `O_NOFOLLOW` where available, preventing a final-component symlink from redirecting unattended replay to another file.
- The descriptor is still checked with `fstat()` and must be a regular file before any bytes are consumed; descriptor cleanup is explicit on all rejection/error paths.
- Commit `9444a06bfa5c3d904d5c399f9e0ee64e99fbde69` replaces the old FIFO test with an unconnected FIFO regression that would expose a blocking-open bug, and adds a no-follow symlink regression on supporting platforms.
- No Actions workflows, credentials, cloud resources, remediation targets, or unrelated repositories were touched.

### Checks / results
- GitHub accepted both implementation and regression commits.
- Static inspection confirms `O_NONBLOCK` is applied before opening the path, `fstat()` still precedes reads, and the 1 MiB + sentinel bound is unchanged.
- The connector runtime does not expose an executable checkout, so the focused MCP gate and new regressions were not executed; no new green claim is made.

### Decisions
1. Special-file safety must cover the open operation itself, not only reads after opening.
2. Use descriptor-level flags for unattended fixture ingestion while preserving ordinary local regular-file behavior.
3. Refuse final-component symlinks where the operating system provides `O_NOFOLLOW`; on platforms without it, the existing opened-descriptor regular-file and bounded-content policies still apply.
4. Continue avoiding GitHub Actions solely to obtain validation because this project explicitly prefers low-noise local checks.

### Blockers / unknowns
- The focused MCP gate still requires an executable checkout: `python scripts/run_stageguard_validation.py --gate "Grafana MCP" --keep-going`.
- Grafana `13.2.1` + official MCP `1.4.1` Docker acceptance, Viewer-token bootstrap, sanitized real response capture, and datasource HTTP-method observation remain pending.
- Connector-authored replay changes are not yet executed.
- Historical full-suite failures/errors still need classification after the focused MCP boundary is green.

## Single best next step
Run the focused `Grafana MCP` validation gate in an executable checkout. Once green, perform the pinned Grafana `13.2.1` + official MCP `1.4.1` Docker smoke, retain only the sanitized semantic capture expected by `runtime/mcp_fixture_replay.py`, and replay it locally to lock the actual current server response shape into regression coverage.
