# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, fail-closed HTTP/operator handling, no-replay reconciliation for post-remediation persistence uncertainty, versioned metric/Loki onboarding activation, recovery-only Grafana rechecks after accepted remediation, fixed-cardinality recovery observability, and stdio-only Grafana MCP launcher enforcement across both production adapters and smoke/acceptance tooling.

Detailed older run history remains in Git history; this file keeps the current invariants, validation baseline, latest run, blockers, and next step.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- StageGuard's production Grafana MCP adapters and smoke/acceptance client are local **stdio-only** subprocess clients. Explicit SSE/streamable-HTTP launchers fail closed, and direct use of the official Docker image requires explicit `-t stdio` before the child process can be spawned.
- Investigation and recovery accept only finite non-boolean numeric metric evidence; malformed samples become unavailable and can never prove diagnosis/recovery.
- Loki corroboration validates adapter envelopes, exact evidence windows, record budgets/shapes, scope, and event identity before corroborating a diagnosis.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; remediation acceptance requires literal boolean `True`.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove recovery.
- Once an accepted provider action has produced `recovery_unverified`, follow-up verification uses a recovery-only path with no remediation client and therefore cannot replay the provider side effect.
- Durable `recovery_unverified` state survives restart and remains eligible only for recovery-only verification; `recovered` is terminal.
- Durable checkpoint/audit failures fail closed; once provider dispatch may have occurred, persistence uncertainty blocks replay.
- Production remediation HTTP requests never follow redirects and do not redirect bearer/idempotency authority.
- Authentication/identity inputs are bounded and attacker-controlled credentials are bounded before comparison.
- Metric activation v2 pins the exact ordered eight-query profile contract; Loki activation v2 pins policy-owned LogQL/limit and bounded preflight evidence.
- The reference Grafana MCP dependency is pinned to `grafana/mcp-grafana:1.4.1`; read-only/tool-surface restrictions are regression-locked.
- Core remediation watchdog clocks are finite native numbers; invalid/backward active clocks fail readiness closed.
- Local audit/checkpoint state is symlink/hard-link/path-substitution hardened and owner-private; POSIX checkpoint access is parent-directory-descriptor bound.
- Local checkpoint parents must not be group- or world-writable, including sticky world-writable directories.
- Recovery observability is fixed-cardinality and provider-detail-free.
- Durable recovery outcome and execution phase must agree; mismatch fails readiness closed and has a critical Grafana alert.
- The browser cockpit trusts the authenticated server-produced recovery contract. Missing, malformed, self-inconsistent, or checkpoint-inconsistent recovery data fails closed and disables lifecycle mutations.
- The browser recovery control uses only `POST /v1/recovery/recheck`; the operator UI must never infer a need to invoke `/v1/execute` when recovery is already `recovery_unverified`.
- Execution uncertainty is resolved only by durable checkpoint reload plus server-owned provider reconciliation and fresh Grafana evidence; callers never supply provider operation identity/state.
- Fast local recovery-safety validation executes the real embedded operator-console JavaScript; missing Node is an explicit validation failure rather than a silently skipped browser safety check.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current committed recovery/API/Grafana/operator/MCP transport regressions remain blocked from repository execution because this runner cannot resolve `github.com`; authenticated connector reads/writes work, but connector commits are not treated as passing tests.

## Run log — 2026-09-14 — MCP smoke/acceptance transport hardening

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected `runtime/mcp_smoke.py`, `runtime/command_line.py`, `runtime/mcp_metric_client.py`, `runtime/tests/test_command_line.py`, and the current runtime test tree.

The previous run had already hardened the shared `split_command` parser used by production Prometheus and Loki MCP adapters, but `runtime/mcp_smoke.py` still called `shlex.split` directly. That meant a custom `STAGEGUARD_MCP_COMMAND` supplied specifically for smoke/acceptance validation could bypass StageGuard's stdio-only policy and attempt to start the official Grafana MCP over SSE/streamable HTTP or start the official Docker image without its required explicit `-t stdio` override.

No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, remediation provider, IAM binding, or GitHub Actions workflow was modified or triggered.

### Exact changes made

1. Updated `runtime/mcp_smoke.py` to import and use the shared `command_line.split_command` parser instead of `shlex.split`.
2. Added `_configured_command`, which validates either the environment-provided `STAGEGUARD_MCP_COMMAND` or an injected command through the same stdio-only policy used by production evidence adapters.
3. Converted launcher parsing/configuration failures into bounded `McpError` messages so unsafe or malformed smoke launchers fail cleanly before `subprocess.Popen` can run.
4. Preserved the safe default `docker compose run --rm -T mcp`, whose Compose service owns the pinned official image and explicit `-t stdio` configuration.
5. Added `runtime/tests/test_mcp_smoke_transport.py` covering the safe Compose default, native stdio default, explicit direct-Docker stdio, direct official Docker without stdio, SSE, streamable HTTP, unknown transport, malformed quoting, and environment-driven overrides.

Commits:
- `520d21f3ed07296e7873d023281053a7794990ca` — Enforce stdio-only launcher in Grafana MCP smoke
- `5e9d80ffcde4327e8fa786815ad86328ded9be07` — Lock MCP smoke to stdio transport

### Checks / results

- Authenticated GitHub connector read/write operations succeeded against `UnknownGod2011/Grafana`.
- Verified the smoke launcher now reaches the same shared parser used by production MCP adapters rather than maintaining an independent parser path.
- Verified the new regression directly exercises `_configured_command`, so network transport configuration is rejected before any `StdioClient`/`subprocess.Popen` construction is necessary.
- Attempted a fresh checkout followed by `python -m unittest runtime.tests.test_command_line runtime.tests.test_mcp_smoke_transport`; checkout failed before tests started with `Could not resolve host: github.com`.
- Therefore this run does **not** claim the committed focused tests green.
- No GitHub Actions workflow was triggered merely to bypass the runner DNS failure.

### Decisions

1. Treat smoke/acceptance tooling as part of the same MCP security boundary as production adapters; diagnostics must not be a network-listener escape hatch.
2. Keep one parser/policy implementation for all configurable MCP child-process launchers.
3. Fail unsafe transport configuration before process spawn and surface a bounded operator-facing error.
4. Keep validation local/focused and avoid adding noisy CI solely for this regression.

### Blockers / unknowns

- This runner still cannot resolve `github.com` for a fresh repository checkout, so the committed focused/full suites cannot currently execute here.
- Recent audit/checkpoint/retention/recovery/Grafana/MCP regressions still require consolidated execution.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**Once checkout is executable, run `runtime.tests.test_command_line` and `runtime.tests.test_mcp_smoke_transport` first, then the focused recovery/API safety suite. If those are green, stop adding transport assertions and triage the historical full-suite failures/errors to identify the highest-severity genuine production defect versus obsolete tests, fixing the first real defect end-to-end.**
