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
- Grafana MCP smoke requests are time-bounded, stdio framing/response integrity fails closed, and individual stdout protocol frames are bounded before JSON parsing.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest checkpoint/acceptance hardening.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires an executable live smoke before a production-ready claim.

## Run log — 2026-09-12 — MCP stdio frame-size hardening

### Inspected at start

Read this `progress.md` completely before deciding what to change. Inspected:
- `runtime/mcp_smoke.py`
- `runtime/tests/test_mcp_smoke_timeout.py`
- `docs/grafana-mcp-evidence-safety.md`

Also reviewed current official MCP SDK transport guidance. Relevant references:
- https://php.sdk.modelcontextprotocol.io/run/stdio/ — official stdio transport exposes `maxLineBytes` and rejects oversized lines.
- https://ruby.sdk.modelcontextprotocol.io/server/transports/ — official stdio transport exposes `max_line_bytes` to bound a newline-delimited frame.
- https://go.sdk.modelcontextprotocol.io/protocol/ — stdio is newline-delimited JSON over stdin/stdout.
- https://github.com/grafana/mcp-grafana — official Grafana MCP repository.

All repository writes in this run were limited to `UnknownGod2011/Grafana`. No unrelated repository, workflow, cloud resource, Grafana instance, Gemini endpoint, or remediation provider was modified.

### Finding

The MCP smoke already bounded request latency and failed closed on malformed JSON-RPC, but the stdout reader used unbounded line iteration. A broken or compromised MCP subprocess could therefore emit an arbitrarily large newline-delimited or unterminated stdout frame and force the client to accumulate a large amount of data before the request timeout meaningfully protected the caller. Request deadlines and frame-size bounds protect different failure modes, so both are needed at this dependency boundary.

### Exact changes made

#### 1. Bounded MCP stdout protocol frames

Commit: `8737b83da2f05e6dffb2f959d03eda0e48818e2d`

`runtime/mcp_smoke.py` now:
- defines a fixed `MAX_STDIO_LINE_CHARS = 1_048_576` acceptance bound;
- reads stdout with `readline(MAX_STDIO_LINE_CHARS + 1)` instead of unbounded line iteration;
- emits a structured `McpError` through the reader queue when a frame exceeds that bound;
- fails the active request before JSON parsing when the oversized-frame marker is received;
- preserves existing request deadlines, strict JSON-RPC validation, notification handling, response-id checks, and subprocess cleanup.

The bound is intentionally fixed rather than made casually configurable. StageGuard's release smoke performs `initialize`, `tools/list`, datasource discovery, and a bounded instant Prometheus query; legitimate frames for that acceptance path should be far below 1 MiB. Raising the trust boundary should require an explicit code review.

#### 2. Added a real-subprocess oversized-frame regression

Commit: `2e919541c25803259333d764a67120af3f83c4ce`

`runtime/tests/test_mcp_smoke_timeout.py` now includes a subprocess that writes `MAX_STDIO_LINE_CHARS + 1` characters to stdout. The regression requires StageGuard to raise the frame-size `McpError` promptly, before the output is passed to JSON parsing. Existing tests for normal replies, notifications, stray stdout, mismatched IDs, invalid JSON-RPC versions, silent-server timeout, and timeout configuration remain intact.

#### 3. Documented the resource-exhaustion boundary

Commit: `2bd04f7eccd6ef534e2b9ce68a6ba088bb9ecc2f`

`docs/grafana-mcp-evidence-safety.md` now records:
- the fixed 1,048,576-character stdout frame ceiling;
- why request deadlines alone do not bound per-frame memory;
- the fail-closed behavior before JSON parsing;
- current official MCP SDK examples that also expose bounded stdio line/frame settings;
- the regression expectation for oversized stdout frames.

### Checks / results

- Direct authenticated GitHub repository inspection and writes succeeded.
- A fresh repository checkout was attempted with `git clone https://github.com/UnknownGod2011/grafana.git`; the local execution environment still failed with `Could not resolve host: github.com`.
- No GitHub Actions workflow was triggered or rerun as a workaround.
- Because the repository checkout remains unavailable, the actual repository unittest module was not executed and there is **no new green repository-suite claim**.
- An isolated subprocess-level proof of the exact bounded-read primitive was executed locally: a child wrote `1,048,577` stdout characters with no newline, the reader used `readline(1,048,577)`, and the oversized frame was detected in `0.447s`. This validates the transport primitive only; it does not replace the committed unittest or live MCP smoke.

### Decisions

1. Keep both request-time and per-frame bounds; they mitigate distinct hang/resource-exhaustion modes.
2. Fail an oversized frame before JSON parsing rather than attempting truncation or recovery, because truncating protocol data could create ambiguous semantics.
3. Keep the smoke frame ceiling fixed in code so a deployment environment cannot silently weaken release acceptance.
4. Preserve strict stdout-as-protocol behavior and continue allowing legitimate JSON-RPC notifications while one request is outstanding.
5. Continue avoiding noisy GitHub Actions merely to work around a transient local DNS/checkout issue.

### Blockers / unknowns

- `runtime.tests.test_mcp_smoke_timeout`, `runtime.tests.test_mcp_smoke_surface`, and `runtime.tests.test_observability_image_pins` still need execution from the actual repository checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required before calling that dependency baseline production-ready.
- It remains to confirm every tool actually exposed by 1.4.1 under StageGuard's exact `datasource,prometheus,loki --disable-write --disable-proxied` configuration carries `readOnlyHint=true`.
- The strengthened Cloud Run bridge six-module set still needs an executable run.
- The execution-reconciliation/operator/Playwright safety set from previous runs still needs a current run.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**As soon as executable checkout/Docker access works, run `runtime.tests.test_mcp_smoke_timeout`, `runtime.tests.test_mcp_smoke_surface`, and `runtime.tests.test_observability_image_pins`, then execute `python runtime/mcp_smoke.py` against pinned Grafana MCP 1.4.1. If those are clean, run the six focused Cloud Run bridge modules and then the private `ADC -> Cloud Run /metrics -> authenticated bridge -> Prometheus up: 1 -> 0 -> 1` acceptance.**
