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
- Grafana MCP smoke requests are time-bounded, stdout JSON-RPC frames are individually bounded, strict framing/response integrity fails closed, and pending stdout frames are held in a fixed-capacity queue so notification/output floods cannot create unbounded process memory growth.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest checkpoint/acceptance hardening.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires an executable live smoke before a production-ready claim.

## Run log — 2026-09-12 — MCP pending-frame queue hardening

### Inspected at start

Read this `progress.md` completely before deciding what to change. Inspected the current default-branch repository state and then reviewed:
- `runtime/mcp_smoke.py`
- `runtime/tests/test_mcp_smoke_timeout.py`
- `docs/grafana-mcp-evidence-safety.md`
- current `main` branch head (`a4254bd64d90e44b8756f059dcb1fbf4d36e0b72` at run start)

All repository writes in this run were limited to `UnknownGod2011/Grafana`. No unrelated repository, workflow, cloud resource, Grafana instance, Gemini endpoint, or remediation provider was modified.

### Finding

The MCP smoke had already bounded two important dimensions: each request has a deadline, and each newline-delimited stdout frame is capped before JSON parsing. However, the reader thread fed those frames into an **unbounded `queue.Queue`**. A broken or compromised MCP subprocess could emit a large stream of individually valid, individually sub-1-MiB notifications faster than the single sequential request consumer could process them. That output could accumulate in process memory without violating either the per-request timeout or per-frame limit. This is a distinct producer/consumer resource-exhaustion boundary.

### Exact changes made

#### 1. Bounded the pending MCP stdout queue

Commit: `cb8174ed6b42da1f984d328c2c2b1f078dd21e2c`

`runtime/mcp_smoke.py` now:
- defines a fixed `MAX_STDOUT_QUEUE_FRAMES = 16` limit;
- constructs the stdout handoff queue with `maxsize=16` rather than leaving it unbounded;
- uses non-blocking `put_nowait` in the stdout reader so the reader thread can never deadlock indefinitely waiting for queue capacity;
- records overflow with a `threading.Event` sentinel and stops reading further protocol data when capacity is exceeded;
- checks the overflow sentinel while waiting for a response and fails closed with a bounded-capacity `McpError` rather than draining an attacker-controlled backlog;
- applies the same non-blocking handoff to oversized-frame errors and EOF markers, preserving the existing subprocess cleanup path;
- retains the existing request deadline, 1,048,576-character frame limit, strict JSON-RPC validation, notification support, response-ID matching, and read-only tool-surface enforcement.

The queue limit is fixed rather than environment-configurable. This smoke has one outstanding request at a time and does not need a deep asynchronous event backlog; increasing the pending-frame trust boundary should require code review.

#### 2. Added a deterministic notification-flood regression

Commit: `90afa2bbee587bfe03810b5321c60ef568847eee`

`runtime/tests/test_mcp_smoke_timeout.py` now includes a real local subprocess that emits `MAX_STDOUT_QUEUE_FRAMES + 1` JSON-RPC notifications before it begins consuming requests. The regression waits for the overflow sentinel, verifies the queue never exceeds its configured capacity, and requires the next request to fail closed with the queue-capacity error. Existing timeout, valid response, notification, dirty stdout, oversized frame, wrong response ID, invalid JSON-RPC version, and constructor validation coverage remains in place.

#### 3. Documented the third stdio resource bound

Commit: `0cb235a996732c5568d59eb589df8afcaaa90d2b`

`docs/grafana-mcp-evidence-safety.md` now describes the MCP stdio safety contract as three independent limits:
1. bounded request time;
2. bounded individual stdout frame size;
3. bounded pending stdout-frame count.

The documentation also explains why notification floods are different from a single oversized frame, why bounded legitimate notifications remain supported, and why the queue depth is intentionally fixed.

### Checks / results

- Direct authenticated GitHub repository inspection and all three repository writes succeeded.
- A fresh checkout was attempted with `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git`; the execution environment still failed with `Could not resolve host: github.com`.
- No GitHub Actions workflow was triggered or rerun as a workaround.
- Because an executable checkout remains unavailable, `runtime.tests.test_mcp_smoke_timeout` was **not** executed from the actual repository and there is no new green repository-suite claim.
- An isolated subprocess proof of the exact new queue primitive was executed locally: a child emitted 17 JSON-RPC notification frames into a queue capped at 16; the overflow sentinel became true and observed queue size remained exactly 16. This validates the producer/consumer bound itself, not the committed unittest module or live Grafana MCP integration.

### Decisions

1. Bound the number of pending protocol frames in addition to request time and per-frame size; all three protect different failure modes.
2. Use non-blocking producer insertion and fail closed on overflow rather than blocking the reader thread, silently dropping notifications, or expanding the queue.
3. Keep the queue limit fixed in code so deployment configuration cannot silently weaken release acceptance.
4. Preserve legitimate JSON-RPC notifications; only sustained output that exceeds the bounded consumer backlog is rejected.
5. Continue avoiding noisy GitHub Actions merely to work around the transient local DNS/checkout issue.

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
