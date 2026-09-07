# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable path covers strict telemetry mapping, metric/Loki activation pins, official Grafana MCP evidence, deterministic diagnosis with Loki corroboration, authenticated incident lifecycle orchestration, optional revision-bound Gemini briefing, approval-gated remediation, Grafana recovery verification, bounded durable audit reconstruction, signed GCS incident checkpoints with strict generation CAS, checkpoint observability, fail-closed conflict recovery, remediation execution-uncertainty recovery, Cloud Run/IAP deployment, operator liveness/readiness/self-observability, and a same-origin operator cockpit with restart-safe lifecycle recovery guidance.

Core invariants:

- Grafana remains the operational evidence plane; infrastructure write credentials remain separate.
- Gemini is advisory only and cannot mutate diagnosis, approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact deterministic evidence revision.
- Fresh investigation clears prior approval/outcome before persisting the new revision.
- Restored checkpoints must match configured telemetry scope and recompute to the persisted evidence revision.
- Production GCS checkpoints require HMAC-SHA-256 authenticity plus strict pinned-generation compare-and-swap.
- Generation conflicts fail closed; losing state is never merged or retried automatically.
- A CAS conflict after remediation contact is execution ambiguity and remains unready until durable-winner reload, provider reconciliation where required, and fresh Grafana evidence.
- A restored production checkpoint with approval but no outcome is also treated as execution-ambiguous; restart can never make that approval executable without provider reconciliation and fresh evidence.
- Reconciliation never replays remediation; the deterministic operation id remains server-owned and is never accepted from the browser/API caller.
- Provider metadata, credentials, Gemini output, Grafana secrets, checkpoint signing material, and provider reconciliation detail are not exposed to the browser.
- `/healthz` proves process liveness only; `/readyz` proves bounded evidence-plane and lifecycle consistency.

## Completed milestones

- Deterministic broadcast telemetry simulator + Prometheus + provisioned Grafana local stack.
- Official Grafana MCP integration with datasource/Prometheus/Loki read tools and write/proxy tools disabled.
- Deterministic incident investigation and bounded Loki corroboration.
- Strict configurable telemetry mapping, metric/Loki preflight, and expiring activation pins.
- Approval-gated remediation and Grafana telemetry-only recovery proof.
- Credential-isolated HTTPS production remediation transport with deterministic idempotency identity.
- Bounded revision-bound Gemini incident-commander briefing layer.
- Verified Google IAP identity provider and bounded Cloud Logging audit sink/reader.
- Dedicated non-root Cloud Run image with embedded official Grafana MCP binary and remediation disabled by default.
- `/healthz`, fail-closed `/readyz`, readiness caching/backoff, and Prometheus-format self-observability.
- Authenticated same-origin operator cockpit and bounded audit timeline.
- Signed GCS lifecycle checkpoints with strict generation CAS, conflict metrics, explicit winner reload, and fail-closed remediation execution uncertainty.
- Restart-safe operator recovery UX exposing only `clear`, `reload_required`, or `reloaded`.
- Provider-neutral, read-only HTTP idempotency reconciliation transport contract with bounded result states.
- Explicit production remediation now requires and wires a dedicated read-only reconciliation endpoint.
- Concrete HTTP transport lifecycle coverage for accepted/not-found/timeout/malformed/repeated reconciliation without remediation replay.
- Restart-safe production approval recovery: restored approval-without-outcome checkpoints fail closed before any external action can be replayed.

## Run log — 2026-09-08 — concrete reconciliation lifecycle + restart-safe approval boundary

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected:

- `runtime/execution_safety.py`;
- `runtime/production_remediation.py`;
- `runtime/http_remediation_transport.py`;
- `runtime/tests/test_execution_safety.py`;
- `runtime/incident_service.py`;
- `runtime/telemetry.py`;
- `runtime/incident_checkpoint.py`;
- `EXECUTION_UNCERTAINTY.md`.

The prior handoff requested full execution-uncertainty tests through the concrete HTTPS transport. While tracing that path, a higher-severity restart gap was found: execution uncertainty existed only in process memory. A process restart with a persisted production approval and no outcome could not prove whether the previous process had already contacted the remediation provider, so restoring that approval as executable risked replaying an external action.

### Exact changes made

Added `runtime/tests/test_execution_safety_http_transport.py`:

- exercises `ExecutionSafeIncidentService` through `AllowlistedProductionRemediationClient` and concrete `HttpRemediationTransport`;
- verifies execution uses exactly one POST before a forced post-provider checkpoint conflict;
- verifies accepted reconciliation uses a bodyless GET, collects fresh evidence, clears stale approval/outcome, and never replays execution;
- verifies reconciliation HTTP 404 maps to bounded `not_found` and never replays execution;
- verifies timeout keeps `execution_uncertain` fail-closed;
- verifies malformed provider documents keep uncertainty blocked and provider detail does not escape the coarse error;
- verifies repeated reconciliation after success performs no provider network request and no remediation replay.

Corrected the concrete lifecycle fixture to the real default telemetry allowlist (`broadcast-alpha` / `uplink-b`) so the production adapter reaches its transport rather than rejecting the target early.

Updated `runtime/execution_safety.py`:

- after base checkpoint restoration/validation, production-style adapters declaring `requires_operation_reconciliation = True` now inspect restored state;
- if the durable checkpoint contains an approval with no outcome, StageGuard derives the deterministic operation id from the restored report + approval and immediately enters `execution_uncertain`;
- the reconciliation phase is `reloaded` because construction already loaded and validated the durable winner;
- `execute_approved()` is therefore blocked after restart before the remediation provider can be contacted;
- reconciliation still requires provider `accepted` or `not_found` plus a fresh Grafana investigation, which clears the stale approval and requires a new human approval for any future execution;
- local/simulator adapters that do not require reconciliation keep their existing restart semantics.

Expanded `runtime/tests/test_execution_safety.py`:

- verifies a restored pending production approval enters `execution_uncertain` without any remediation execution call;
- verifies provider reconciliation + fresh evidence clears that restored approval while execution call count remains zero;
- verifies local adapter restart behavior is unchanged.

Updated `EXECUTION_UNCERTAINTY.md`:

- documents the crash/restart ambiguity boundary;
- documents why a restored approval-without-outcome cannot safely prove that the provider was never contacted;
- documents the conservative production restart policy and its deliberate tradeoff: a genuinely unused approval may be invalidated after restart rather than risking duplicate external side effects;
- documents the new concrete HTTPS lifecycle regression coverage.

### Commits produced this run

- `48b1f66b` — add concrete remediation transport uncertainty lifecycle tests
- `c4c1c34a` — fix concrete remediation test telemetry allowlist
- `903cc62a` — fail closed on restored production approvals after restart
- `0848340d` — test restart-safe production approval recovery
- `a9db7219` — document restart-safe execution uncertainty

### Tests / checks / results

Attempted credential-free local validation with:

```text
python -m unittest tests.test_execution_safety_http_transport tests.test_execution_safety tests.test_http_remediation_transport tests.test_production_remediation
```

The checkout failed before Python started because the execution container still could not resolve `github.com` (`Could not resolve host: github.com`). Therefore the Python suite is **not claimed as executed successfully** in this run.

Static review caught and fixed one concrete fixture error before handoff: the production client originally used a non-default target and would have rejected execution before transport invocation.

No GitHub Actions workflow was intentionally triggered, rerun, or modified. No Grafana, Loki, Gemini, IAP, Cloud Logging, GCS, Secret Manager, operator, or remediation credential/resource was used.

### Decisions made

1. **Restart ambiguity is equivalent to execution ambiguity for production adapters.** If durable state cannot prove that a pending approved action was never sent, StageGuard must not make it executable after process restart.
2. **Safety beats approval preservation.** A genuinely unused production approval may be discarded after restart through reconciliation + fresh evidence; silently replaying a potentially completed external action is unacceptable.
3. **The durable checkpoint remains provider-detail-free.** Restart safety derives the deterministic operation id from already-authenticated report + approval state rather than persisting provider responses or credentials.
4. **Local development remains ergonomic.** Simulator/local adapters are not forced through provider reconciliation on ordinary restart.
5. **Concrete reconciliation is read-only and replay-proof.** Accepted, not-found, timeout, malformed, and repeated reconciliation paths are tested around the transport boundary without constructing a second remediation command.

### Current blockers / unknowns

- The deterministic Python suite remains unexecuted in this environment because the container cannot resolve GitHub for checkout.
- Real-GCS two-instance acceptance, Cloud Run/IAP browser acceptance, real provider idempotency lookup, and real Grafana MCP metric+Loki acceptance still require external credentials/resources.
- The restart-safe rule is intentionally conservative because checkpoint schema v1 does not persist a durable pre-execution/side-effect phase marker. A future schema evolution could preserve unused approvals more precisely while retaining replay safety.

## Single best next step

**Introduce a durable, authenticated remediation execution-phase marker in checkpoint schema v2 (for example `approved`, `dispatching`, `resolved`) with backward-compatible v1 restore semantics, so StageGuard can distinguish a genuinely unused restored approval from a possibly dispatched operation without weakening the current fail-closed restart guarantee. Add migration/round-trip/tamper tests and keep provider response detail out of the checkpoint.**

## Previous run — 2026-09-08 — production reconciliation bootstrap wiring

Production bootstrap was updated so explicit remediation requires and wires `STAGEGUARD_REMEDIATION_RECONCILIATION_ENDPOINT`, with separate execution/reconciliation endpoints and fail-closed HTTPS validation. Targeted local validation could not run because the container could not resolve GitHub. The next handoff from that run requested concrete transport lifecycle coverage, completed above.
