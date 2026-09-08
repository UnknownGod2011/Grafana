# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable path includes configurable telemetry mapping, Prometheus/Loki/Grafana MCP evidence, deterministic diagnosis, revision-bound Gemini briefing, authenticated approval-gated remediation, Grafana recovery verification, signed checkpoint persistence with optimistic concurrency, provider idempotency reconciliation, Cloud Run/IAP deployment, operator readiness/metrics, a same-origin recovery cockpit, and checkpoint schema v2 with a durable pre-side-effect remediation phase.

Core safety invariants:

- Grafana is the evidence plane; infrastructure write credentials remain isolated from Grafana/MCP access.
- Gemini is advisory and cannot mutate approval, remediation, or recovery state.
- Human approval is single-use and bound to an exact evidence revision.
- Production remediation uses a deterministic idempotency identity and never automatically replays ambiguous external side effects.
- Phase-capable stores persist `dispatching` before provider contact; `approved` therefore proves dispatch has not begun.
- Restored `dispatching` and legacy-v1 pending approvals fail closed and require provider reconciliation plus fresh Grafana evidence.
- GCS checkpoints are HMAC-authenticated and use strict generation compare-and-swap.
- `/readyz` fails closed for checkpoint conflict or execution uncertainty; execution-phase telemetry is fixed-cardinality and provider-detail-free.
- Concrete remediation reconciliation is GET-only and cannot carry a remediation body.

## Completed milestones

- Deterministic media telemetry simulator plus local Prometheus/Grafana stack.
- Official Grafana MCP integration with bounded Prometheus/Loki evidence tools.
- Configurable telemetry mappings, activation preflight, and strict evidence scope.
- Approval-gated remediation and telemetry-only recovery proof.
- Credential-isolated HTTPS remediation transport with deterministic idempotency identity.
- Provider-neutral GET-only reconciliation with bounded `accepted` / `not_found` / `unknown` states.
- Revision-bound Gemini incident-commander briefing layer.
- Verified Google IAP identity, Cloud Logging audit integration, and Cloud Run deployment path.
- Durable checkpoint recovery, strict CAS conflict handling, and operator recovery cockpit.
- Checkpoint schema v2 phases: `none`, `approved`, `dispatching`, `resolved`, with conservative legacy restore.
- Fixed-cardinality execution-phase readiness/Prometheus observability.
- Crash-boundary fault-injection regression matrix for approval persistence, dispatch barrier persistence, provider execution, Grafana recovery verification, and resolved checkpoint persistence.
- Real spawned-process SIGKILL acceptance coverage using `JsonCheckpointStore` across the two most dangerous remediation boundaries.
- Real loopback TLS coverage for `HttpRemediationTransport` execution and GET-only reconciliation.
- Spawned-process SIGKILL acceptance routed through the concrete HTTPS remediation transport and a local idempotent provider server.

## Run log — 2026-09-08 — concrete HTTPS process-death replay safety

### Inspected at start

Read `progress.md` completely before deciding what to change. Then inspected:

- `runtime/http_remediation_transport.py` for HTTPS validation, POST execution, GET-only reconciliation, bounded responses, and error handling;
- `runtime/tests/test_http_remediation_transport.py` for existing mocked transport coverage;
- `runtime/tests/test_subprocess_crash_recovery.py` for the existing spawned-process SIGKILL acceptance model;
- `runtime/production_remediation.py` for allowlisting, deterministic operation identity, retry bounds, and provider reconciliation;
- `runtime/execution_safety.py` for the durable `dispatching` barrier and restart semantics;
- `runtime/incident_service.py` and `runtime/telemetry.py` to verify the default production/uplink scope used by the lifecycle.

### Exact changes made

1. Updated `runtime/http_remediation_transport.py` with an optional injectable `urlopen` callable.
   - Production behavior is unchanged when it is omitted: `urllib.request.urlopen` is still resolved at call time.
   - Endpoint validation still requires absolute credential-free HTTPS URLs.
   - No insecure-TLS production switch was added.
   - The field is excluded from dataclass repr/equality and validated as callable when supplied.
   - Existing monkey-patched tests remain compatible because the standard opener is resolved per call when no override is present.

2. Added `runtime/tests/test_http_remediation_tls_integration.py`.
   - Generates an ephemeral one-day self-signed certificate at test time with local `openssl`.
   - Starts a real loopback `ThreadingHTTPServer` wrapped in TLS.
   - Exercises the concrete `HttpRemediationTransport` over an actual HTTPS socket.
   - Proves execution performs one POST with a non-empty body and reconciliation performs one bodyless GET.
   - Proves a previously unseen operation reconciles as `not_found` without any POST.
   - Uses a test-only SSL context through the injected opener; production TLS policy is not weakened.

3. Added `runtime/tests/test_http_subprocess_crash_recovery.py`.
   - Uses the real `JsonCheckpointStore`, `ExecutionSafeIncidentService`, `AllowlistedProductionRemediationClient`, `HttpRemediationTransport`, a local TLS provider, `multiprocessing` with `spawn`, and POSIX `SIGKILL`.
   - Case A kills the child after durable `dispatching` but before the HTTP POST; restart reconciles with GET/404 -> `not_found`, gathers fresh Grafana evidence, clears the stale approval, and records zero POSTs.
   - Case B lets the real HTTPS provider accept the POST and then SIGKILLs the child before StageGuard can finish execution; restart reconciles the exact deterministic operation ID with GET -> `accepted`, gathers fresh Grafana evidence, clears the stale approval, and proves the POST count remains exactly one.
   - The provider records and compares the `Idempotency-Key` to the operation ID so operation-identity continuity is explicit.
   - A second restart is asserted synchronized with no approval and therefore no executable stale action.
   - The test is skipped when POSIX `SIGKILL` or `openssl` is unavailable.

4. Corrected the new subprocess harness to use the actual default StageGuard telemetry scope: production `broadcast-alpha` and affected uplink `uplink-b`.

### Tests / checks / results

Attempted a fresh credential-free local checkout and targeted run without invoking GitHub Actions:

```text
python -m unittest \
  tests.test_http_remediation_transport \
  tests.test_http_remediation_tls_integration \
  tests.test_http_subprocess_crash_recovery \
  tests.test_subprocess_crash_recovery -v
```

The container failed before Python started:

```text
fatal: unable to access 'https://github.com/UnknownGod2011/Grafana.git/': Could not resolve host: github.com
```

Therefore the new integration/acceptance tests are **not claimed as executed successfully** in this environment. No GitHub Actions workflow was intentionally triggered, rerun, or modified. No Grafana, Gemini, GCS, IAP, Cloud Logging, Secret Manager, operator, or production remediation credentials/resources were used.

### Decisions made

1. **Inject the opener, not an insecure TLS flag.** This provides deterministic network testing while keeping production endpoint/TLS policy strict.
2. **Use a real TLS socket rather than another mocked `urlopen`.** The concrete request method, headers, body presence, HTTP status handling, and GET-only reconciliation now cross the HTTP stack.
3. **Kill after the concrete transport receives provider acceptance.** This models the dangerous boundary where the provider side effect happened but the lifecycle still has only durable `dispatching`.
4. **Keep provider state external to StageGuard.** Restart learns only `accepted` / `not_found` through the read-only reconciliation contract and never adopts provider detail into checkpoint state.
5. **Require fresh Grafana evidence after either reconciliation result.** Reconciliation resolves ambiguity; it never resurrects the old approval or proves recovery by itself.

### Current blockers / unknowns

- Local deterministic Python execution remains blocked because the container cannot resolve `github.com` for checkout.
- The new TLS tests depend on a local `openssl` executable and POSIX SIGKILL for the hard-crash cases; they skip rather than emulate those guarantees when unavailable.
- Real GCS two-instance acceptance, Cloud Run/IAP browser acceptance, live Grafana MCP acceptance, and a real provider idempotency endpoint still require external credentials/resources.
- Malformed/timeout provider reconciliation is covered at unit/in-process layers, but the spawned-process concrete-HTTPS harness currently covers the authoritative `accepted` and `not_found` restart outcomes.

## Single best next step

**Extend the concrete HTTPS subprocess harness with fail-closed provider ambiguity cases: make the local reconciliation endpoint deliberately return malformed JSON, a wrong operation-id echo, an unknown state, and a bounded timeout; prove `reconcile_execution_uncertainty()` refuses to clear `execution_uncertain`, readiness remains blocked, no second POST occurs, and a later valid GET can safely recover using fresh Grafana evidence.**

## Previous run — 2026-09-08 — real process-death replay-safety acceptance

Added `runtime/tests/test_subprocess_crash_recovery.py` using a spawned interpreter, real `JsonCheckpointStore`, fsynced modeled provider state, and POSIX SIGKILL after durable `dispatching` and after modeled provider acceptance. Restart required reconciliation plus fresh Grafana evidence and never replayed remediation.

## Previous run — 2026-09-08 — remediation crash-boundary fault matrix

Added the in-process five-boundary crash matrix covering approval persistence, `dispatching` persistence, provider failure, Grafana recovery-verification failure, and resolved checkpoint CAS failure with explicit provider-call counts and readiness assertions.

## Previous run — 2026-09-08 — execution-phase observability

Added bounded execution-phase API/readiness/Prometheus observability and conservative fail-closed behavior for phase-unaware custom checkpoint stores.
