# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, fail-closed HTTP/operator handling, no-replay reconciliation for post-remediation persistence uncertainty, versioned metric/Loki onboarding activation, recovery-only Grafana rechecks after accepted remediation, fixed-cardinality recovery observability, and stdio-only Grafana MCP launcher enforcement.

Detailed older run history remains in Git history; this file keeps the current invariants, validation baseline, latest run, blockers, and next step.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- StageGuard's production Grafana MCP adapters are local **stdio-only** subprocess clients. Explicit SSE/streamable-HTTP launchers fail closed, and direct use of the official Docker image requires explicit `-t stdio` before the child process can be spawned.
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

## Run log — 2026-09-14 — Grafana MCP stdio transport boundary

### Inspected at start

Read this `progress.md` completely before selecting work. Inspected repository/root contents, the historical release report, the recursive runtime/test tree, `runtime/telemetry.py`, `runtime/tests/test_telemetry.py`, `runtime/mcp_metric_client.py`, `runtime/mcp_log_client.py`, `runtime/mcp_smoke.py`, `runtime/command_line.py`, `runtime/tests/test_command_line.py`, `docker-compose.yml`, and the existing Grafana MCP evidence-safety documentation.

Also checked the current official `grafana/mcp-grafana` release and upstream `v1.4.1` README. `v1.4.1` remains the latest release and was published 2026-09-11. Upstream documents `stdio`, `sse`, and `streamable-http` transports. Critically, the native binary defaults to stdio while the official Docker image defaults to a network transport unless `-t stdio` is supplied explicitly. The repository Compose service already supplies `-t stdio`, publishes no MCP port, disables writes/proxied tools, and enables only `datasource,prometheus,loki`.

That exposed a genuine configuration safety gap: production metric/log adapters accept `STAGEGUARD_MCP_COMMAND`, so an operator could replace the safe Compose launcher with a direct `docker run grafana/mcp-grafana:1.4.1` command. StageGuard's Python client would expect stdio, but the child image could start a network MCP listener until the request timeout/cleanup path killed it.

No unrelated repository, cloud resource, Grafana instance, Gemini endpoint, remediation provider, IAM binding, or GitHub Actions workflow was modified or triggered.

### Exact changes made

1. Hardened `runtime/command_line.py`, the shared launcher parser used by production Prometheus and Loki MCP adapters.
2. Added explicit stdio-only transport enforcement for `-t`, `--transport`, `-t=...`, and `--transport=...` forms.
3. Explicitly reject SSE, streamable HTTP, unknown non-stdio transports, duplicate transport declarations, and missing transport values before `subprocess.Popen` can run.
4. Direct `grafana/mcp-grafana:<tag>` and `grafana/mcp-grafana@<digest>` launchers now require explicit stdio. The native `mcp-grafana` binary may omit the flag because upstream documents stdio as its native default.
5. Preserved the repository launcher `docker compose run --rm -T mcp`; its Compose service already owns the explicit `-t stdio` policy.
6. Expanded `runtime/tests/test_command_line.py` with transport-boundary regressions covering native binary defaults, Compose, direct Docker image tags/digests, all supported stdio flag forms, SSE/streamable-HTTP rejection, unknown transports, duplicates, and missing values.
7. Added `docs/mcp-stdio-transport-safety.md` with the threat model, upstream `v1.4.1` attribution, supported launcher examples, reference Compose contract, and regression expectations.

Commits:
- `7ef013da2d1d0b4b37c0bb5f92aa7e98626e0a78` — Fail closed on network Grafana MCP launcher transports
- `0b6977e7671876f260a8f531a883db1fd1d4ce52` — Lock StageGuard MCP to stdio transport
- `ee8a2e417094d42b3081099e9c00b24d1ec2e759` — Document StageGuard MCP stdio transport boundary

### Checks / results

- Authenticated GitHub connector read/write operations succeeded against `UnknownGod2011/Grafana`.
- Verified the production metric and Loki adapters both construct `STAGEGUARD_MCP_COMMAND` through `split_command`, so the new transport interlock is on both production evidence paths.
- Cross-checked the default Compose launcher: the MCP service is pinned to `grafana/mcp-grafana:1.4.1`, explicitly uses `-t stdio`, publishes no MCP network port, uses `--disable-write`, `--disable-proxied`, and a narrow tool category set.
- Independently executed the new parser logic against safe and unsafe command matrices. Safe stdio/native/Compose forms passed; direct Docker without stdio, SSE, streamable HTTP, unknown transport, duplicate transport, and missing-value cases all failed with the intended bounded errors.
- The full committed unittest module was not executed from a repository checkout because this runner still cannot resolve `github.com`. Therefore this run does **not** claim the committed test suite green.
- No GitHub Actions workflow was triggered merely to bypass the runner DNS failure.

### Decisions

1. Treat MCP transport as part of the security architecture. StageGuard needs a private local evidence subprocess, not a network MCP server.
2. Reject unsafe transport configuration before process spawn rather than depending on a request timeout to clean up an accidentally listening child process.
3. Preserve the documented native-binary stdio default while being stricter for direct official Docker-image launch, whose upstream default differs.
4. Keep the reference Compose path as the preferred local/free deployment because it already centralizes the least-privilege image, tool, and transport flags.
5. Do not add a CI workflow for this regression; keep validation local/focused until the existing checkout/network issue clears.

### Blockers / unknowns

- This runner still cannot resolve `github.com` for a fresh repository checkout, so the committed focused/full suites cannot currently execute here.
- `runtime/mcp_smoke.py` still parses its optional launcher independently rather than through the newly hardened shared parser. It uses the safe Compose default, but a custom smoke-only `STAGEGUARD_MCP_COMMAND` should be moved onto the same stdio-only parser boundary next.
- Recent audit/checkpoint/retention/recovery/Grafana regressions still require consolidated execution.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- The real disposable private Cloud Run acceptance still requires a private StageGuard service, least-privilege ADC invoker identity, and Docker.
- Historical full-suite failures/errors remain untriaged; there is still no full-suite green claim.

## Single best next step

**Move `runtime/mcp_smoke.py` onto the shared `split_command` stdio-only launcher boundary and add a regression proving smoke-time custom launchers cannot select a network transport; then, when repository checkout becomes executable, run that focused transport test plus the recovery/API safety suites before triaging the historical full-suite failures into genuine defects versus obsolete tests.**
