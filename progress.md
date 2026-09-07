# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable path covers strict telemetry mapping, metric/Loki activation pins, official Grafana MCP evidence, deterministic diagnosis with Loki corroboration, authenticated incident lifecycle orchestration, optional revision-bound Gemini briefing, approval-gated remediation, Grafana recovery verification, bounded durable audit reconstruction, signed GCS incident checkpoints with strict generation CAS, checkpoint observability, fail-closed conflict recovery, remediation execution-uncertainty recovery, Cloud Run/IAP deployment, operator liveness/readiness/self-observability, and a same-origin operator cockpit with restart-safe lifecycle recovery guidance.

Core invariants:

- Grafana remains the operational evidence plane; infrastructure write credentials remain separate.
- Gemini is advisory only and cannot mutate diagnosis, approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact deterministic evidence revision.
- Fresh investigation clears prior approval/outcome before persisting the new revision.
- Audit history and mutable lifecycle state remain separate persistence concerns.
- Restored checkpoints must match configured telemetry scope and recompute to the persisted evidence revision.
- Production GCS checkpoints require HMAC-SHA-256 authenticity plus strict pinned-generation compare-and-swap.
- Generation conflicts fail closed; the losing process never retries or merges approval-bearing state automatically.
- After a checkpoint conflict, lifecycle work remains blocked until the durable winner is explicitly loaded and fully revalidated.
- A CAS conflict that occurs after a remediation adapter was contacted is treated as execution ambiguity, not merely storage contention.
- Execution ambiguity remains unready after durable-winner reload until provider reconciliation (when required) and a fresh Grafana investigation invalidate the stale approval.
- The API and browser never accept a caller-supplied remediation operation id for reconciliation; the deterministic id stays server-owned.
- Provider remediation metadata/details, credentials, Gemini output, Grafana secrets, checkpoint signing material, and provider reconciliation results are not exposed to the browser.
- Standard Cloud Run production remediation remains disabled by default.
- `/healthz` proves process liveness only; `/readyz` proves bounded evidence-plane and lifecycle consistency.
- The operator cockpit disables investigation, briefing, approval, and execution whenever checkpoint state is `conflicted` or `execution_uncertain`.
- Execution-uncertainty recovery is restart-safe in the browser: authenticated lifecycle responses expose only `clear`, `reload_required`, or `reloaded`, and unknown values fail closed.

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
- Versioned incident lifecycle checkpoints with owner-only JSON local storage and signed GCS production storage.
- Strict GCS pinned-generation CAS semantics plus isolated two-writer acceptance harness.
- Checkpoint conflict metrics and explicit durable-winner reload/revalidation.
- Fail-closed remediation execution-uncertainty service with provider idempotency reconciliation contract.
- Production bootstrap/API integration for execution uncertainty, including unready state, bounded metric, and authenticated argument-free reconciliation.
- Operator-cockpit recovery UX for `conflicted` and `execution_uncertain`, with action controls disabled while blocked and server-owned reload/reconciliation endpoints only.
- Authenticated low-cardinality execution reconciliation phase exposed to the cockpit so reload-vs-reconcile guidance survives browser refreshes.

## Run log — 2026-09-08 — refresh-safe execution uncertainty recovery

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected:

- repository metadata/default branch and current head (`01df99be56db4fcabbaef1a0cd1872bc8ebc7e3a` at run start);
- `runtime/api.py`;
- `runtime/execution_safety.py`, including the existing `execution_reconciliation_state()` state machine;
- `runtime/operator_console.py`;
- `runtime/tests/test_execution_safety_api.py`;
- `runtime/tests/test_operator_console.py`;
- `OPERATOR_CONSOLE.md`.

The highest-value gap matched the prior handoff: server enforcement already knew whether uncertain execution required durable reload or was ready for reconciliation, but authenticated HTTP status exposed only coarse `checkpoint_state`. A browser refresh therefore lost the distinction and could offer reconciliation too early, relying on a 409 response rather than explicit server state.

### Exact changes made

Updated `runtime/api.py`:

- added `_execution_reconciliation_state()` as a bounded adapter around the safer service method;
- exposes only three low-cardinality values: `clear`, `reload_required`, or `reloaded`;
- base `IncidentService` runtimes map to `clear`;
- exceptions, unknown values, or future unsupported values fail closed to `reload_required`;
- added `_lifecycle_view()` so authenticated `GET /v1/incident`, `POST /v1/checkpoint/reload`, and `POST /v1/execution/reconcile` return the same lifecycle envelope;
- the envelope contains only `incident`, coarse `checkpoint_state`, and `execution_reconciliation_state`;
- no remediation operation id, provider result (`accepted`/`not_found`/`unknown`), endpoint, target, credential, or GCS generation is exposed;
- bumped the HTTP server version from `StageGuard/0.10` to `StageGuard/0.11`.

Updated `runtime/operator_console.py`:

- added a browser-owned `executionReconciliationState` containing only the bounded API value;
- unknown/malformed values fail closed to `reload_required`;
- while `execution_uncertain` + `reload_required`, the reload button is enabled and reconciliation is disabled;
- while `execution_uncertain` + `reloaded`, reload is disabled and reconciliation is enabled;
- a refresh now consumes `data.execution_reconciliation_state`, so the correct recovery step survives browser reload/tab refresh;
- reload/reconciliation success responses also consume the bounded phase rather than inferring it from message text;
- reconciliation remains impossible unless both `checkpoint_state === execution_uncertain` and phase is exactly `reloaded`;
- recovery calls still submit empty JSON objects and no action-replay surface was added.

Updated `runtime/tests/test_execution_safety_api.py`:

- proves authenticated incident status returns `reload_required` before durable-winner reload;
- proves the response excludes the deterministic operation id and provider result vocabulary;
- proves lifecycle recovery state is not disclosed without authentication;
- proves reload returns `reloaded`;
- proves a fresh authenticated `GET /v1/incident` still returns `reloaded` after reload, making the workflow browser-refresh-safe;
- proves successful reconciliation returns `clear`, clears stale approval/outcome, and still contacts the remediation provider only once across the full conflict/reload/reconcile path.

Updated `runtime/tests/test_operator_console.py`:

- verifies the cockpit reads `execution_reconciliation_state` from authoritative status responses;
- verifies reload/reconcile buttons are gated by `reload_required` vs `reloaded` respectively;
- verifies unknown reconciliation values fail closed;
- retains redaction checks proving the browser never exposes or accepts a remediation operation id;
- retains mutation-error checks requiring an authoritative status refresh.

### Commits produced this run

- `979fd778` — expose bounded execution reconciliation state
- `7618074c` — test bounded execution reconciliation phase API
- `af36cf08` — make uncertain execution cockpit refresh-safe
- `e79ad41b` — test refresh-safe uncertainty cockpit phases
- `72260b1d` — fix reconciliation fail-closed assertion

### Tests / checks / results

No GitHub Actions workflow was created, triggered, rerun, or modified.

Attempted a fresh local checkout for credential-free execution, but the container again failed before Python started:

```text
fatal: unable to access 'https://github.com/UnknownGod2011/Grafana.git/': Could not resolve host: github.com
```

Therefore the Python test suite is **not claimed as executed successfully** in this run. Source and tests were written through the authenticated GitHub connector and the relevant files were re-inspected through repository APIs.

No Grafana, Loki, Gemini, IAP, Cloud Logging, GCS, Secret Manager, operator, or remediation credential/resource was used.

### Decisions made

1. **Expose phase, not provider state.** The browser needs to know only which recovery step is legal, not whether the provider reported accepted/not-found/unknown.
2. **Unknown phase values fail closed.** A backend/frontend version skew cannot accidentally enable reconciliation; the browser treats an unrecognized value as requiring reload.
3. **One lifecycle envelope.** Incident status, reload, and reconciliation responses now use the same bounded state shape, reducing inference and stale-state bugs.
4. **Server authority remains primary.** Browser gating is usability and defense-in-depth; the service still rejects illegal reconciliation before reload.
5. **No replay semantics changed.** Reconciliation never re-executes remediation, and no operation id becomes caller-controlled.

### Current blockers / unknowns

- The deterministic Python suite remains unexecuted in this environment because direct checkout still fails DNS resolution for `github.com`.
- The default `HttpRemediationTransport` still has no provider-specific reconciliation API. This remains intentionally fail-closed; production remediation transports must implement a real idempotency lookup contract.
- The real-GCS two-instance acceptance harness and Cloud Run/IAP browser acceptance still require external credentials/resources.
- Grafana MCP readiness and full metric+Loki investigation still need acceptance against a real Grafana Cloud or self-hosted instance.
- The operator documentation predates this bounded phase field and should be refreshed when the next operator-facing recovery change is made; implementation behavior is captured here and in regression tests.

## Single best next step

**Add a provider-neutral remediation reconciliation adapter contract with a credential-free fake/reference HTTP implementation that can look up a deterministic idempotency key without replaying the action, then test `accepted`, `not_found`, timeout/error, malformed-response, and duplicate-reconciliation paths end-to-end through `ExecutionSafeIncidentService`. This closes the largest remaining production blocker while keeping provider credentials and operation ids server-owned.**
