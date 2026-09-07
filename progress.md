# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable path covers strict telemetry mapping, metric/Loki activation pins, official Grafana MCP evidence, deterministic diagnosis with Loki corroboration, authenticated incident lifecycle orchestration, optional revision-bound Gemini briefing, approval-gated remediation, Grafana recovery verification, bounded durable audit reconstruction, signed GCS incident checkpoints with strict generation CAS, checkpoint observability, fail-closed conflict recovery, remediation execution-uncertainty recovery, Cloud Run/IAP deployment, operator liveness/readiness/self-observability, and a same-origin operator cockpit with explicit lifecycle-recovery controls.

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
- Provider remediation metadata/details, credentials, Gemini output, Grafana secrets, and checkpoint signing material are not persisted or exposed to the browser.
- Standard Cloud Run production remediation remains disabled by default.
- `/healthz` proves process liveness only; `/readyz` proves bounded evidence-plane and lifecycle consistency.
- The operator cockpit disables investigation, briefing, approval, and execution whenever checkpoint state is `conflicted` or `execution_uncertain`.

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

## Run log — 2026-09-07 — operator lifecycle-recovery cockpit

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected:

- repository metadata/default branch and current head (`fe0a80bc14a8fa5945489a76343629b28f90c488` at run start);
- `runtime/operator_console.py`;
- `runtime/api.py` and its existing `checkpoint_state` contract;
- `runtime/execution_safety.py`, including `execution_reconciliation_state()` and the explicit durable-reload requirement;
- `runtime/tests/test_operator_console.py`;
- `OPERATOR_CONSOLE.md` and the prior execution-uncertainty handoff.

The highest-value gap matched the previous handoff: the API already failed closed, but the browser cockpit still rendered normal investigation/approval/execution controls and had no dedicated recovery workflow for checkpoint conflict or uncertain remediation execution.

### Exact changes made

Updated `runtime/operator_console.py`:

- added a dedicated fail-closed lifecycle recovery panel;
- consumes the existing bounded `checkpoint_state` returned by `GET /v1/incident` and by the recovery endpoints;
- recognizes `conflicted` and `execution_uncertain` as lifecycle-blocking states;
- disables investigation, Gemini briefing, approval revision entry, approval, and execution while blocked;
- keeps refresh and audit timeline viewing available so operators can inspect bounded state/provenance without mutating lifecycle state;
- for `conflicted`, guides the operator to `POST /v1/checkpoint/reload`;
- for `execution_uncertain`, guides the operator through durable checkpoint reload and then `POST /v1/execution/reconcile`;
- both recovery calls send only `{}` and never accept an operation id, provider state, target, action, evidence revision, or arbitrary reconciliation input;
- explicitly states that reconciliation does not replay remediation;
- after any lifecycle mutation failure, refreshes authoritative server checkpoint state so a stale browser tab cannot leave dangerous controls enabled after a CAS race;
- after a successful reload that remains `execution_uncertain`, keeps the safety block visible and instructs the operator that reconciliation is still required;
- after successful reconciliation, renders the fresh investigation returned by the server, restoring controls only after server state is synchronized;
- added bounded recovery styling without external assets or dependencies.

Updated `runtime/tests/test_operator_console.py`:

- verifies the lifecycle recovery panel and both recovery controls are present;
- verifies browser logic recognizes both blocked checkpoint states;
- verifies investigation and approval input are disabled while blocked;
- verifies execution gating includes the lifecycle safety block;
- verifies the cockpit calls only the server-owned reload and reconciliation endpoints;
- verifies recovery POST bodies are empty objects;
- verifies no concrete `operation_id` field is present in cockpit HTML or JavaScript;
- verifies the UI explicitly communicates that reconciliation does not replay remediation;
- verifies lifecycle mutation failure paths refresh authoritative checkpoint state rather than leaving stale controls enabled.

### Commits produced this run

- `b8a49d65` — add fail-closed operator recovery cockpit
- `91f5e270` — test fail-closed cockpit recovery controls
- `eecd3038` — fix cockpit redaction regression assertion

### Tests / checks / results

No GitHub Actions workflow was created, triggered, rerun, or modified.

Attempted credential-free local validation with:

```text
python -m unittest tests.test_operator_console tests.test_execution_safety_api tests.test_bootstrap_execution_safety
```

A fresh checkout was attempted first, but the container failed before Python started:

```text
fatal: unable to access 'https://github.com/UnknownGod2011/Grafana.git/': Could not resolve host: github.com
```

Therefore the new Python tests are **not claimed as executed successfully** in this run. The changed files were written through the authenticated GitHub connector and structurally re-inspected through repository APIs.

No Grafana, Loki, Gemini, IAP, Cloud Logging, GCS, Secret Manager, operator, or remediation credential/resource was used.

### Decisions made

1. **Browser gating mirrors, but never replaces, server authority.** The UI disables dangerous controls based on bounded checkpoint state; every server lifecycle method remains independently fail-closed.
2. **Mutation errors force a status refresh.** A post-provider CAS conflict can happen after the browser has already initiated execution, so the tab must immediately re-fetch authoritative checkpoint state rather than trust its previous incident snapshot.
3. **Recovery inputs remain server-owned.** The cockpit submits empty JSON objects only. It never displays or accepts a remediation operation id, target, provider state, action name, or arbitrary reconciliation payload.
4. **Execution uncertainty remains blocked after reload.** Reload resolves durable checkpoint ownership only; the UI keeps approval/execution disabled until reconciliation plus fresh Grafana investigation completes.
5. **No replay control exists.** The uncertain-execution workflow exposes reconciliation only; there is no browser action that retries or replays remediation.
6. **Read-only operator visibility stays available.** Refresh and bounded audit viewing remain usable during safety blocks so operators can understand state without mutating it.

### Current blockers / unknowns

- The deterministic Python suite remains unexecuted in this environment because direct checkout still fails DNS resolution for `github.com`.
- The default `HttpRemediationTransport` still has no provider-specific reconciliation API. This remains intentionally fail-closed; production remediation transports must implement a real idempotency lookup contract.
- The real-GCS two-instance acceptance harness and Cloud Run/IAP browser acceptance still require external credentials/resources.
- Grafana MCP readiness and full metric+Loki investigation still need acceptance against a real Grafana Cloud or self-hosted instance.
- The cockpit currently consumes only coarse `checkpoint_state`. The service already has a bounded `execution_reconciliation_state()` (`reload_required` / `reloaded` / `clear`), but the HTTP API does not expose it yet. Server enforcement is safe, but exposing that bounded state would let the cockpit distinguish “reload still required” from “reload completed, reconcile now” across browser refreshes without relying on endpoint failure messages.

## Single best next step

**Expose the existing bounded `execution_reconciliation_state()` through authenticated incident/recovery responses and use it in the cockpit to make the uncertainty workflow restart-safe across browser refreshes: show exactly `reload required` versus `ready to reconcile`, while continuing to exclude operation ids/provider details. Add API + cockpit regression coverage proving the state is low-cardinality, authenticated, and cannot enable action replay.**
