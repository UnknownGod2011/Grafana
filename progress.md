# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The current vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded diagnosis, optional Gemini briefing, revision-bound approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated metrics bridging, stale/scrape detection, pinned local acceptance images, strict Prometheus/MCP evidence parsing, structured evidence-unavailable abstention, fail-closed operator handling for observability-plane outages, payload-integrity validation on the private Cloud Run metrics bridge, and an opt-in disposable Prometheus acceptance harness for the complete private Cloud Run scrape chain including local bridge failure/recovery.

Core invariants:
- Grafana/MCP is read-only evidence access; infrastructure write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Approval is exact-revision-bound and single-use.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove it.
- Durable checkpoint/audit integrity failures fail closed.
- Loss of observability must never be reclassified as a positive remediation deadline breach.
- Ambiguous, malformed, nonnumeric, or non-finite evidence must never be interpreted as healthy evidence.
- Expected evidence-plane transport/protocol failures become sanitized abstention, not diagnosis.
- Programming/configuration defects remain visible exceptions.
- Partial, missing, or unavailable evidence must never reach infrastructure mutation.
- The browser must never turn evidence unavailability into an actionable diagnosis or expose provider failure detail.
- An authenticated HTTP 200 alone is not sufficient bridge readiness; the body must prove it is an unambiguous StageGuard runtime-safety exposition.
- Cloud Run metrics acceptance must never grant IAM, print credentials, mutate incidents, or require making StageGuard public.
- Recovery acceptance may interrupt only the local metrics bridge; it must not mutate Cloud Run, IAM, or StageGuard lifecycle state.

## Run log — 2026-09-11 — local metrics bridge failure/recovery acceptance

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected:
- `runtime/cloud_run_metrics_acceptance.py`
- `runtime/tests/test_cloud_run_metrics_acceptance.py`
- `runtime/cloud_run_metrics_bridge.py`
- `docs/cloud-run-metrics-bridge-safety.md`

The previous handoff identified the highest-value safe next step as extending the private Cloud Run acceptance path with a bounded local bridge outage/recovery proof. That work does not require changing Cloud Run, IAM, incident state, or remediation state.

### Exact changes made

#### Extended private Cloud Run acceptance to prove `up: 1 -> 0 -> 1`

Updated `runtime/cloud_run_metrics_acceptance.py`.

The acceptance path is now:

```text
anonymous Cloud Run /metrics rejection
  -> ADC-authenticated Cloud Run /metrics + StageGuard sentinel validation
  -> local authenticated bridge ready
  -> disposable Prometheus observes up == 1
  -> stop only the local bridge
  -> Prometheus observes the same target as up == 0
  -> same authenticated CloudRunMetricsClient successfully fetches upstream /metrics while bridge is down
  -> restart bridge on the exact same port
  -> Prometheus observes up == 1 again
```

Implementation details:
- generalized Prometheus target-state waiting into `wait_for_prometheus_up(..., expected=0|1, ...)`;
- rejects non-binary expected states at the acceptance helper boundary;
- retained `fetch_prometheus_up()` as the focused `up == 1` wrapper used by existing regressions;
- added `_start_bridge()` and `_stop_bridge()` helpers so the bridge lifecycle is explicit and cleanup remains centralized;
- after initial `up == 1`, shuts down and closes only the local bridge server;
- requires Prometheus to observe exactly one finite `up == 0` sample before recovery is attempted;
- calls the same production `CloudRunMetricsClient.fetch()` while the local bridge is down, proving the private Cloud Run + ADC/IAM path remains valid and the acceptance did not mutate upstream state;
- restarts the bridge on the exact original port so Prometheus cannot recover by accidentally scraping a different target;
- requires Prometheus to observe exactly one finite `up == 1` sample after restart;
- reports initial, outage, and recovered `up` values separately;
- preserves `finally` cleanup for both Prometheus and whichever bridge instance is currently active.

Commit:
- `54c5634a3a512d2c41198c5df1a99900ed446429` — add bounded bridge failure recovery acceptance

#### Added credential-free recovery regressions

Updated `runtime/tests/test_cloud_run_metrics_acceptance.py`.

New coverage proves:
- `wait_for_prometheus_up()` can require an exact single `up == 0` sample;
- expected target state is restricted to binary `0/1`;
- the complete acceptance orchestration requests Prometheus states in the exact order `[1, 0, 1]`;
- upstream `client.fetch()` is called twice: once before exposing the bridge and once while the bridge is intentionally down;
- the recovered bridge is started on the exact original port;
- ordering is fail-closed: Prometheus must observe bridge-down before the upstream continuity fetch and before recovery;
- existing Docker safety, ambiguity/non-finite rejection, anonymous privacy check, and CLI sanitization contracts remain represented.

Commit:
- `5b0c7c11d264c0cbf50e3bab827fb5548741dd3c` — test metrics bridge outage recovery lifecycle

#### Updated operational safety documentation

Updated `docs/cloud-run-metrics-bridge-safety.md` so a passing disposable-project run now explicitly proves ten ordered conditions rather than stopping at initial `up == 1`.

The documentation now states that:
- only the local bridge is interrupted;
- Cloud Run is never stopped/restarted/reconfigured;
- IAM is never changed;
- the private upstream is revalidated during the local outage;
- recovery must occur on the same bridge port;
- credential-free tests cover the ordered `1 -> 0 -> 1` contract.

Commit:
- `43c54732dc381e87ac49222ba90876f44e3055cf` — document local bridge failure recovery acceptance

### Checks / results

Attempted a fresh executable checkout and focused test run:

```bash
git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard
cd /tmp/stageguard
python -m unittest runtime.tests.test_cloud_run_metrics_acceptance runtime.tests.test_cloud_run_metrics_bridge
```

The execution container again failed before checkout with:

```text
Could not resolve host: github.com
```

Therefore no claim is made that the updated acceptance regression module, existing bridge tests, browser acceptance, full unittest suite, or Docker rehearsal is green in this run.

A local Python runtime check confirmed `ThreadingHTTPServer.allow_reuse_address == 1`, so the same-port bridge restart design is compatible with Python's shipped HTTP server behavior.

Repository writes succeeded through the connected GitHub integration. No GitHub Actions workflow was created, triggered, rerun, or modified. No GCP/IAM/Cloud Run, Grafana Cloud, Gemini, audit, checkpoint, incident, approval, remediation, or recovery resource was changed.

### Decisions

1. Interruption is scoped to the local authenticated metrics bridge only; acceptance must never simulate failure by revoking IAM or stopping Cloud Run.
2. Prometheus must observe `up == 0` before any restart, otherwise the test would not prove scraper-visible failure detection.
3. The authenticated upstream is rechecked while the bridge is down to prove the Cloud Run service and invocation path remained intact.
4. Recovery must use the same local port because Prometheus's target is fixed; this prevents a different accidental target from satisfying recovery.
5. The target-state helper accepts only `0` or `1` and still requires a single finite series, preserving the existing ambiguity fail-closed rule.
6. No CI wiring was added; real Cloud Run acceptance remains opt-in to avoid credentials, cloud cost, and noisy Actions usage.

### Blockers / unknowns

- The updated `runtime/tests/test_cloud_run_metrics_acceptance.py` still needs execution in a runnable checkout.
- The real acceptance harness requires an existing private StageGuard Cloud Run test service, working ADC for a least-privilege invoker identity, and Docker.
- The Playwright evidence-unavailable browser acceptance still needs execution with Chromium.
- The complete pinned Prometheus 3.13.3 + Grafana 13.2.1 watchdog rehearsal still needs a current run after the latest hardening.
- Historical full-suite failures/errors have not yet been re-triaged; no full-suite green claim exists.

## Single best next step

**Execute the focused bridge/acceptance tests and then run `python runtime/cloud_run_metrics_acceptance.py` against a disposable private StageGuard Cloud Run service with a dedicated least-privilege `roles/run.invoker` identity, capturing whether the real path completes `up: 1 -> 0 -> 1` while the authenticated upstream remains valid during the local outage.**

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from last executable run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, but it predates the latest acceptance hardening.
- Official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0` before the latest evidence-availability changes.
- Incident flow baseline: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.
