# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, strict evidence parsing, evidence-unavailable abstention, fail-closed HTTP/operator handling, explicit no-replay reconciliation for post-remediation persistence uncertainty, and versioned metric/Loki onboarding activation.

This file is intentionally compact; detailed earlier run history remains in Git history.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove recovery.
- Durable checkpoint/audit failures fail closed and uncommitted state is not operator-visible lifecycle authority.
- Once provider dispatch may have occurred, persistence uncertainty blocks replay.
- Browser/API/onboarding/CLI surfaces must not expose provider failure detail or turn evidence loss into actionable state.
- Expected evidence transport/protocol/datasource failures cross runtime boundaries as `EvidenceUnavailable`; unexpected programming/policy exceptions fail loudly inside the runtime and process-level entrypoints fail closed without exposing raw exception text.
- Metric and Loki activation records are bounded, schema/version validated, expiry constrained, datasource/contract pinned, and rejected when malformed.
- Telemetry activation v2 pins the exact profile-derived ordered eight-query contract and normalized observed samples.
- Loki activation v2 requires the exact policy-owned LogQL/limit contract and a bounded successful preflight with no error detail.
- Private Cloud Run metric requests reject redirects and keep token audience/target boundaries explicit.
- Runtime metric readiness requires an unambiguous StageGuard safety sentinel, not merely HTTP 200.
- A metrics bridge bound beyond loopback requires explicit network-bind opt-in, inbound bearer authentication, strict bearer-token syntax, and a minimum 32-character credential.
- The private Cloud Run acceptance harness uses one bounded selector-safe Prometheus job identity consistently in YAML and PromQL.
- The reference Grafana MCP dependency is pinned to `grafana/mcp-grafana:1.4.1`; server-side write/proxy restrictions and live `readOnlyHint=true` validation are regression-locked.
- Grafana MCP smoke requests are time-bounded; stdout JSON-RPC frames and pending-frame queue growth are bounded and framing/response integrity fails closed.
- Cloud Run remediation/recovery execution watchdog configuration is bounded to 1-600 seconds.
- Cloud Run checkpoint HMAC keys are bounded to 32-512 UTF-8 bytes and reject boundary whitespace/control characters.
- Telemetry profiles require independent healthy comparators.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating the latest activation/checkpoint/acceptance hardening.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke before a production-ready claim.
- Recent MCP hardening added request deadlines, strict JSON-RPC framing/response-ID validation, a 1,048,576-character frame cap, and a 16-frame pending stdout queue; current repository regressions still need a runnable checkout.

## Recently completed work

### Metric onboarding / activation

- Enforced independent healthy comparator mappings.
- Onboarding catches only `EvidenceUnavailable`, redacts provider detail, rejects non-finite samples, and fails unexpected programming/policy exceptions loudly.
- Metric activation v2 verifies the exact ordered profile-derived preflight contract and hashes normalized observed sample values.
- Persisted/manual activation authority validates canonical SHA-256 digests, trimmed production identity, integer non-negative timestamps, strict expiry ordering, a seven-day maximum lifetime, and strict explicit-clock types.

Recent commits:
- `dfe6a5cf5164aa1553d6b146487ff7517dc6294d` — Harden telemetry activation record validation
- `4e6e3264e88ef19c80de7e522544273cf52ff0d4` — Add activation record integrity regressions

### Loki onboarding / activation

- `preflight_loki()` catches only `EvidenceUnavailable` and emits stable redacted detail; unexpected programming/policy exceptions propagate.
- Loki activation v2 requires the exact policy-owned LogQL/limit contract, bounded line count/window metadata, no truncation/error detail, canonical persisted-record shape, and bounded validity.

Recent commits:
- `09b7a9e52e290cfd7b4c4113374aaa7388d47fb6` — Harden Loki preflight and activation authority
- `abddb80c002041024d5cfa0cdd4acc12a2e61c0f` — Add Loki activation safety regressions

### Preflight CLI boundary

- The process-level preflight CLI no longer serializes raw exception messages. Startup/config/MCP/provider failures now return only `ready=false`, the stable message `preflight failed`, and the exception class name.
- This prevents secret-bearing endpoint URLs, bearer tokens, backend response text, and similar provider detail from crossing the operator-visible CLI boundary.
- Regression coverage checks both the pure failure payload and the actual `main()` error path.

Recent commits:
- `7de4377a0822f388a1b26273f7de8d23da97e917` — Redact preflight CLI failure details
- `678744f574216c07af65122d904dc0774e024ac5` — Add preflight CLI redaction regressions

### Cloud Run / MCP safety retained

- Cloud Run execution watchdog: 1-600 seconds in runtime and deployment helper.
- Checkpoint HMAC key: 32-512 UTF-8 bytes with whitespace/control rejection.
- Hermetic deploy-script regression prevents invalid watchdog values from reaching `gcloud`.
- Private metrics acceptance job identity is allowlisted and bounded before any Cloud Run/Docker action.
- Grafana MCP smoke has request deadlines, strict JSON-RPC/version/response-ID validation, 1 MiB frame cap, 16-frame pending queue cap, read-only surface enforcement, and image pin regressions.

## Run log — 2026-09-13 — preflight CLI secret-redaction boundary

### Inspected at start

Read this `progress.md` completely before deciding what to change. Inspected repository metadata and reviewed:
- `runtime/preflight.py`
- `runtime/onboarding.py` behavior via `runtime/tests/test_onboarding.py`
- `runtime/activation.py`
- `runtime/log_activation.py`
- `runtime/bootstrap.py`
- `runtime/README.md`

No unrelated repository, GitHub Actions workflow, cloud resource, Grafana instance, Gemini endpoint, IAM binding, or remediation provider was modified.

### Finding

The underlying metric and Loki onboarding functions had already been hardened to redact expected evidence-source failures, but `runtime/preflight.py` still wrapped the complete flow in `except Exception` and printed `f"{type(exc).__name__}: {exc}"`. Constructor failures, malformed provider responses, config/parser failures, or unexpected MCP errors can contain endpoint URLs, credentials, backend response bodies, or other sensitive detail. That contradicted the repository's operator-surface redaction invariant.

### Exact changes made

1. Added `_failure_payload(exc)` in `runtime/preflight.py`.
2. The CLI now returns only:
   - `ready: false`
   - `error: "preflight failed"`
   - `error_type: <exception class>`
3. Raw exception text is never serialized by this process-level error path.
4. Added `runtime/tests/test_preflight_cli.py` with regressions proving:
   - secret-bearing exception messages are absent from serialized failure output;
   - `main()` returns exit code 2 and emits only the safe envelope when telemetry/profile startup fails.

### Checks / results

- Authenticated GitHub reads/writes succeeded and both commits landed on `UnknownGod2011/Grafana` main.
- A fresh executable checkout was attempted with `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git`.
- The execution runner still failed before checkout with `Could not resolve host: github.com`.
- No GitHub Actions workflow was triggered or rerun merely to bypass that transient DNS failure.
- The exact new failure-envelope primitive was independently syntax/redaction checked locally and passed.
- Because a real repository checkout was unavailable, `runtime.tests.test_preflight_cli` and the broader focused suite are **not yet claimed green**.

### Decisions

1. Treat the CLI as an operator-visible security boundary, not a debugging traceback surface.
2. Preserve exception class names for coarse diagnosis while suppressing exception text.
3. Keep detailed provider/MCP diagnostics out of stdout JSON; protected logging can be added separately if needed.
4. Continue avoiding noisy GitHub Actions solely to compensate for runner DNS failure.

### Blockers / unknowns

- `runtime.tests.test_preflight_cli`, `runtime.tests.test_activation`, `runtime.tests.test_log_activation`, `runtime.tests.test_onboarding`, `runtime.tests.test_cloud_run_metrics_acceptance`, `runtime.tests.test_telemetry`, `runtime.tests.test_cloudrun_entrypoint`, and `runtime.tests.test_deploy_cloud_run_script` still need a current repository run.
- MCP timeout/surface/image-pin regressions still need an actual repository run.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The strengthened Cloud Run bridge and execution-reconciliation/operator/Playwright safety sets still need current execution.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**As soon as executable checkout works, run `python -m unittest runtime.tests.test_preflight_cli runtime.tests.test_activation runtime.tests.test_log_activation runtime.tests.test_onboarding runtime.tests.test_cloud_run_metrics_acceptance runtime.tests.test_telemetry runtime.tests.test_cloudrun_entrypoint runtime.tests.test_deploy_cloud_run_script -v`. Fix any regressions before changing another production boundary. If clean, run the MCP timeout/surface/image-pin regressions and the live pinned Grafana MCP 1.4.1 smoke, then proceed to the private `ADC -> Cloud Run /metrics -> authenticated bridge -> Prometheus up: 1 -> 0 -> 1` acceptance.**
