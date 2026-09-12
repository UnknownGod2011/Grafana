# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, strict evidence parsing, evidence-unavailable abstention, fail-closed HTTP/operator handling, and explicit no-replay reconciliation for post-remediation persistence uncertainty.

Core invariants retained:
- Grafana/MCP is read-only evidence access; infrastructure write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove recovery.
- Durable checkpoint/audit failures fail closed and uncommitted state is not operator-visible lifecycle authority.
- Once provider dispatch may have occurred, persistence uncertainty blocks replay.
- Browser/API surfaces must not expose provider failure detail or turn evidence loss into actionable state.
- Private Cloud Run metric requests reject redirects and keep token audience/target boundaries explicit.
- Runtime metric readiness requires an unambiguous StageGuard safety sentinel, not merely HTTP 200.
- A metrics bridge bound beyond loopback requires explicit network-bind opt-in, inbound bearer authentication, strict bearer-token syntax, and a minimum 32-character credential.
- The reference Grafana MCP dependency is pinned to `grafana/mcp-grafana:1.4.1`; server-side write/proxy restrictions are regression-locked; the live smoke rejects any advertised MCP tool that is not explicitly annotated `readOnlyHint=true`.
- Grafana MCP smoke requests are time-bounded and the stdio protocol stream fails closed on framing/response-integrity violations.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest checkpoint/acceptance hardening.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires an executable live smoke before a production-ready claim.

## Run log — 2026-09-12 — MCP stdio protocol-integrity hardening

### Inspected at start

Read this `progress.md` completely before deciding what to change. Inspected `runtime/mcp_smoke.py`, `runtime/tests/test_mcp_smoke_timeout.py`, and `docs/grafana-mcp-evidence-safety.md` on the repository default branch. Also reviewed current MCP stdio guidance confirming that stdout is the protocol channel and ordinary logging belongs on stderr.

Relevant references reviewed:
- https://modelcontextprotocol.io (MCP project documentation)
- https://ts.sdk.modelcontextprotocol.io/v2/get-started/first-server (official TypeScript SDK guidance: stdout is the protocol channel; use stderr for logs)
- https://py.sdk.modelcontextprotocol.io/get-started/real-host/ (official Python SDK host guidance describing stray stdout as protocol corruption)
- https://github.com/grafana/mcp-grafana (official Grafana MCP repository)

All repository writes in this run were limited to `UnknownGod2011/Grafana`. No unrelated repository, workflow, cloud resource, Grafana instance, Gemini endpoint, or remediation provider was modified.

### Finding

The previous bounded stdio client silently skipped malformed/non-JSON stdout and silently skipped responses whose JSON-RPC id did not match the one outstanding StageGuard request. Because StageGuard's smoke client is deliberately sequential and has only one request in flight, those conditions are not useful concurrency behavior: they indicate a corrupted protocol stream, buggy server/wrapper, or an invalid response. Silently ignoring them could turn an immediate integrity failure into a misleading timeout and make dependency acceptance harder to diagnose.

### Exact changes made

#### 1. Fail closed on corrupted MCP stdout

Commit: `2316cb3668fe340aa855e9ad545e8ac20921b46e`

`runtime/mcp_smoke.py` now:
- rejects non-JSON stdout immediately instead of skipping it;
- rejects non-object JSON messages;
- requires every incoming protocol message to declare `jsonrpc="2.0"`;
- permits legitimate JSON-RPC notifications while waiting for a response;
- rejects an id-bearing response whose id differs from the single outstanding request;
- rejects messages that are neither a valid notification nor an id-bearing response;
- keeps the existing per-request deadline and subprocess cleanup behavior unchanged.

This makes stray stdout logging or protocol desynchronization a direct acceptance failure rather than something that is hidden behind the timeout path.

#### 2. Added stdio integrity regressions

Commit: `ec67b7a0c344ee96c479638723f4034844a2e190`

Expanded `runtime/tests/test_mcp_smoke_timeout.py` to cover:
- a normal matching JSON-RPC response;
- a legitimate notification followed by the expected response;
- non-JSON stdout failing closed;
- an unexpected response id failing closed;
- an invalid JSON-RPC version failing closed;
- the existing silent-server timeout behavior;
- timeout configuration validation and constructor safety checks.

### Checks / results

- Direct authenticated GitHub repository inspection and writes succeeded.
- A fresh checkout was attempted before making changes with:
  `python -m unittest runtime.tests.test_mcp_smoke_timeout runtime.tests.test_mcp_smoke_surface runtime.tests.test_observability_image_pins`
- The environment again failed before checkout with `Could not resolve host: github.com`.
- No GitHub Actions workflow was triggered or rerun as a workaround.
- Because the actual repository could not be checked out, the newly committed tests were not executed in this run and there is **no new green repository-suite claim**.

### Decisions

1. Treat stdout as a strict MCP protocol channel; malformed lines are integrity failures, not ignorable noise.
2. Because this smoke client is sequential with exactly one outstanding request, a different response id is a protocol violation and should fail immediately.
3. Continue allowing valid server notifications while a response is outstanding.
4. Preserve bounded request deadlines as defense against a server that sends no protocol message at all.
5. Avoid noisy GitHub Actions merely to work around a transient local DNS/checkout problem.

### Blockers / unknowns

- `runtime.tests.test_mcp_smoke_timeout`, `runtime.tests.test_mcp_smoke_surface`, and `runtime.tests.test_observability_image_pins` still need execution from the actual repository checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required before calling that dependency baseline production-ready.
- It remains to confirm that every tool actually exposed by 1.4.1 under StageGuard's exact `datasource,prometheus,loki --disable-write --disable-proxied` configuration carries `readOnlyHint=true`.
- The strengthened Cloud Run bridge six-module set still needs an executable run.
- The execution-reconciliation/operator/Playwright safety set from previous runs still needs a current run.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**As soon as executable checkout/Docker access works, run `runtime.tests.test_mcp_smoke_timeout`, `runtime.tests.test_mcp_smoke_surface`, and `runtime.tests.test_observability_image_pins`, then execute `python runtime/mcp_smoke.py` against pinned Grafana MCP 1.4.1. If those are clean, run the six focused Cloud Run bridge modules and then the private `ADC -> Cloud Run /metrics -> authenticated bridge -> Prometheus up: 1 -> 0 -> 1` acceptance.**
