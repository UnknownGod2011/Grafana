# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable path now includes strict telemetry mapping, metric/Loki activation pins, official Grafana MCP evidence, deterministic diagnosis with Loki corroboration, authenticated lifecycle orchestration, optional revision-bound Gemini briefing, approval-gated remediation, Grafana recovery verification, bounded durable audit reconstruction, signed GCS checkpoints with strict generation CAS, fail-closed conflict recovery, remediation execution reconciliation, Cloud Run/IAP deployment, operator health/readiness/self-observability, a same-origin recovery cockpit, checkpoint schema v2 with a durable pre-side-effect execution phase, and bounded execution-phase observability.

Core invariants:

- Grafana remains the operational evidence plane; infrastructure write credentials remain separate.
- Gemini is advisory only and cannot mutate diagnosis, approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact deterministic evidence revision.
- Production remediation uses a deterministic idempotency identity and never automatically replays an ambiguous side effect.
- Checkpoint schema v2 persists only a bounded execution phase (`none`, `approved`, `dispatching`, `resolved`); provider detail and operation ids remain outside durable checkpoint state.
- A production provider is never contacted until `dispatching` has been durably persisted when the store supports the v2 phase barrier.
- A v2 `approved` checkpoint proves dispatch has not started and can safely survive restart.
- A restored `dispatching` checkpoint or legacy-v1 pending approval is execution-ambiguous and requires reconciliation plus fresh Grafana evidence.
- Phase-unaware/custom checkpoint stores retain conservative ambiguity semantics: once execution enters the provider path, any later exception or checkpoint conflict is treated as execution-uncertain.
- Production GCS checkpoints require HMAC-SHA-256 authenticity plus strict generation compare-and-swap.
- `/healthz` proves process liveness only; `/readyz` also requires evidence-plane and lifecycle consistency.
- Execution-phase telemetry is fixed-cardinality and excludes incident, operation, target, endpoint, credential, and provider-response identity.

## Completed milestones

- Deterministic broadcast telemetry simulator + Prometheus + provisioned Grafana local stack.
- Official Grafana MCP integration with read-only datasource/Prometheus/Loki evidence tools.
- Deterministic incident investigation with bounded Loki corroboration.
- Strict configurable telemetry mapping, activation preflight, and expiring activation pins.
- Approval-gated remediation and Grafana telemetry-only recovery proof.
- Credential-isolated HTTPS remediation transport with deterministic idempotency identity.
- Revision-bound Gemini incident-commander briefing layer.
- Verified Google IAP identity and bounded Cloud Logging audit integration.
- Non-root Cloud Run image with embedded official Grafana MCP binary.
- `/healthz`, fail-closed `/readyz`, readiness caching/backoff, and Prometheus self-observability.
- Authenticated operator cockpit, bounded audit timeline, conflict reload, and execution reconciliation UX.
- Signed GCS lifecycle checkpoints with strict generation CAS and fixed-label observability.
- Provider-neutral GET-only reconciliation transport with bounded `accepted` / `not_found` / `unknown` states.
- Explicit production reconciliation endpoint wiring and concrete no-replay lifecycle coverage.
- Checkpoint schema v2 durable remediation execution phase with backward-compatible v1 restore.
- Fixed-cardinality execution-phase metrics/readiness diagnostics and restored fail-closed compatibility for phase-unaware stores.

## Run log — 2026-09-08 — execution-phase observability + phase-unaware fail-closed fix

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected:

- `runtime/api.py` self-observability and readiness composition;
- `runtime/execution_safety.py` restart/reconciliation state machine;
- `runtime/tests/test_execution_phase_v2.py`;
- `runtime/tests/test_execution_safety.py`;
- existing checkpoint-v2 handoff and the requested crash-boundary observability next step.

### Exact changes made

Updated `runtime/execution_safety.py`:

- added `execution_checkpoint_phase()` returning only the fixed enum `none`, `approved`, `dispatching`, `resolved`, `legacy_unknown`, or `unknown`;
- ordinary synchronized state derives phase from the in-memory lifecycle snapshot;
- execution-uncertain state reports the authenticated/restored barrier phase instead of incorrectly deriving `approved` from a still-pending approval;
- restored `dispatching` and legacy-v1 `legacy_unknown` remain directly distinguishable without exposing operation/provider identity;
- after successful reconciliation and fresh Grafana investigation the public phase returns to `none`;
- fixed a v2 compatibility regression discovered during static review: phase-unaware/custom checkpoint stores now again mark **any exception after entering `super().execute_approved()`** as execution-uncertain, because provider execution/verification may already have occurred;
- preserved the crucial distinction that a phase-capable v2 pre-dispatch CAS failure occurs before the `try`/provider path and therefore remains an ordinary checkpoint conflict with no provider contact;
- phase-unaware ambiguity reports only `unknown`, never synthesized `dispatching`, because that store cannot prove the durable barrier existed.

Updated `runtime/api.py`:

- added bounded `_execution_checkpoint_phase()` with fail-closed `unknown` fallback;
- `/readyz` now includes `checks.remediation_execution_phase` using only the fixed enum;
- readiness fallback reports `unknown` rather than provider/internal detail;
- `/metrics` now emits one-hot `stageguard_remediation_execution_phase{phase="..."} 0|1` for all six fixed labels;
- retained the existing `stageguard_remediation_execution_uncertain` and checkpoint-conflict gauges;
- no incident id, production id, target, operation id, endpoint, credential, provider response, generation, actor, or user-controlled label is added.

Updated `runtime/tests/test_execution_phase_v2.py`:

- verifies `approved` before dispatch;
- verifies `resolved` after successful execution;
- verifies v2 approved restart remains `approved` and executable;
- verifies restored `dispatching` reports `dispatching` while blocked;
- verifies successful reconciliation plus fresh evidence returns to `none`;
- verifies legacy-v1 pending approval reports `legacy_unknown`.

Added `runtime/tests/test_execution_phase_observability.py`:

- verifies all six fixed labels are always emitted and exactly one is active;
- verifies execution uncertainty forces readiness false while exposing only `dispatching`;
- verifies synchronized approval remains ready with `approved` diagnostics;
- verifies invalid or throwing phase providers fail closed to `unknown`;
- verifies obvious high-cardinality/sensitive identifiers are absent from the metric output.

### Commits produced this run

- `235d7b8f` — expose bounded remediation execution phase
- `77a7333a` — expose fixed-label remediation execution phase telemetry
- `e046e2ac` — test bounded execution phase observability
- `70d8d071` — add execution phase metrics/readiness tests
- `7d031d93` — tighten telemetry redaction assertions
- `8adce18b` — restore fail-closed ambiguity for phase-unaware stores

### Tests / checks / results

Attempted targeted credential-free validation with:

```text
python -m unittest tests.test_execution_phase_v2 tests.test_execution_phase_observability tests.test_execution_safety
```

A fresh checkout again failed before Python started because the execution container could not resolve `github.com` (`Could not resolve host: github.com`). Therefore the Python suite is **not claimed as executed successfully**.

Static compatibility review did find and fix a meaningful regression before handoff: after the v2 dispatch-barrier change, the exception handlers only entered execution uncertainty when `dispatch_barrier` was true. That would have broken the documented conservative semantics for legacy/custom phase-unaware stores after provider contact. The corrected code makes every exception arising after entering the base execution path ambiguous; the v2 pre-dispatch CAS failure remains outside that path and cannot contact the provider.

No GitHub Actions workflow was intentionally triggered, rerun, or modified. No Grafana, Loki, Gemini, IAP, Cloud Logging, GCS, Secret Manager, operator, or remediation credential/resource was used.

### Decisions made

1. **One-hot fixed labels, not dynamic labels.** Execution phase has exactly six bounded values, making it safe for Prometheus/Grafana cardinality.
2. **Readiness diagnostics may expose phase, not identity.** `dispatching`/`legacy_unknown`/`unknown` are operationally useful without disclosing incident or provider detail.
3. **Unknown must fail closed.** Unexpected phase implementations never become `approved` or `resolved` by fallback.
4. **The v2 barrier must not weaken custom-store safety.** Stores that cannot prove `dispatching` still treat any post-provider exception as ambiguous and surface only `unknown`.
5. **Pre-dispatch conflict remains distinct.** A conflict while persisting the v2 barrier happens before provider contact and is not mislabeled execution uncertainty.

### Current blockers / unknowns

- The deterministic Python suite remains unexecuted in this environment because the container cannot resolve GitHub for checkout.
- Real-GCS two-instance acceptance, Cloud Run/IAP browser acceptance, real provider idempotency lookup, and real Grafana MCP metric+Loki acceptance still require external credentials/resources.
- The current test suite covers major states but does not yet inject a failure at every individual crash boundary in a phase-capable store.

## Single best next step

**Add a phase-capable fault-injection checkpoint/provider harness covering every crash boundary (`approved` save → `dispatching` save → provider call → Grafana recovery verification → `resolved` save`) and assert, for each injected failure/restart, the exact provider-call count, durable phase, readiness state, reconciliation requirement, and whether a new human approval is required. This should explicitly prove that pre-dispatch failure never contacts the provider and every post-barrier ambiguity can never replay it.**

## Previous run — 2026-09-08 — checkpoint schema v2 durable dispatch barrier

Introduced `stageguard.incident-checkpoint.v2`, authenticated execution phases, the durable pre-side-effect `dispatching` barrier, safe restart of genuinely unused v2 approvals, conservative legacy-v1 restore, and checkpoint-v2 regression coverage. The current run adds bounded operator observability and restores the intended conservative behavior for phase-unaware custom stores.
