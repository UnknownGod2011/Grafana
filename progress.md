# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence plane. The current vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, restart reconciliation, operator UI, production deployment hardening, runtime watchdog observability, and authenticated Cloud Run metrics ingestion.

Core invariants remain unchanged:
- Grafana/MCP is read-only evidence access; infrastructure write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Approval is exact-revision-bound and single-use.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove it.
- Durable checkpoint/audit integrity failures fail closed.

## Run log — 2026-09-11 — watchdog alert recovery acceptance

### Inspected at start

Read `progress.md` completely first, then inspected `runtime/watchdog_observability_acceptance.py`, `runtime/tests/test_grafana_runtime_observability.py`, `runtime/grafana/provisioning/alerting/stageguard-watchdog.yml`, and `docs/runtime-metrics-ingestion.md`.

The previous run's strongest unblocked gap was confirmed: the local observability acceptance utility proved `idle -> overdue -> alert firing`, but returned the fixture to idle only as cleanup. It did not prove that Prometheus ingested recovery or that Grafana actually cleared the StageGuard watchdog alert. A stuck/latched alert could therefore pass the rehearsal.

### Research / attribution

Checked current official Grafana material before changing the acceptance contract:
- Grafana — View active notifications: https://grafana.com/docs/grafana/latest/alerting/monitor-status/view-active-notifications/
- Grafana — Configure notifications / Alertmanager architecture: https://grafana.com/docs/grafana/latest/alerting/configure-notifications/
- Grafana Labs 2026 note confirming the Alertmanager API remains available while the legacy UI changes: https://grafana.com/whats-new/2026-05-15-alerting--the-legacy-alertmanager-ui-is-no-longer-available-in-grafana-cloud/

The acceptance tool continues to use the Grafana Alertmanager v2 active-alert endpoint already used by the project. No third-party code was copied.

### Exact changes made

#### Full watchdog alert lifecycle acceptance

Updated `runtime/watchdog_observability_acceptance.py` so a PASS now requires the complete bounded lifecycle:

1. set fixture `idle` and observe `deadline_exceeded=0` in Prometheus;
2. set fixture `overdue` and observe `deadline_exceeded=1`;
3. observe the StageGuard watchdog alert as active in Grafana;
4. explicitly set fixture back to `idle`;
5. observe `deadline_exceeded=0` again in Prometheus;
6. require the StageGuard watchdog alert to disappear from a valid Grafana active-alert response before declaring PASS.

Added `--resolve-timeout` with a bounded 35-second default. The existing `finally` cleanup remains, so failure anywhere still attempts to return the fixture to idle.

#### Fail-closed Grafana response parser

Added a testable `grafana_alert_active_from_payload()` boundary:
- only a JSON list is accepted as an active-alert response;
- each alert must be an object;
- `labels` and `annotations` must be objects when present;
- the StageGuard alert can be matched by the committed alert title or committed summary annotation;
- unrelated active alerts do not prevent StageGuard from being considered resolved;
- malformed/unexpected API shapes raise instead of being interpreted as `False`/resolved.

This matters specifically on the recovery edge: an HTML error body, object-shaped API response, or malformed alert entry must never create a false recovery PASS.

#### Regression tests

Added `runtime/tests/test_watchdog_observability_acceptance.py` covering:
- title-based active alert recognition;
- summary-based recognition;
- unrelated active alerts;
- empty active-alert list as resolved;
- fail-closed handling for invalid root response shapes;
- fail-closed handling for malformed alert entries;
- rejection of remote, credentialed, path-bearing, query-bearing, and HTTPS endpoints by the local acceptance loopback guard;
- acceptance of `127.0.0.1` and `localhost` development origins.

#### Documentation

Updated `docs/runtime-metrics-ingestion.md` to document the full healthy -> firing -> resolved acceptance lifecycle, the fail-closed response-shape rule, the bounded resolution timeout, and the fact that unrelated active Grafana alerts do not block this rule-specific recovery check.

### Commits this run

- `8efe14640e4529de0f04efc2fa6915809fa57faa` — verify watchdog alert recovery in acceptance rehearsal
- `a377ba2ea8ca150f7bce0eaf7e9056c1b57521c9` — test watchdog acceptance alert lifecycle parsing
- `a12d65d461525bdcda06a3e4c1b70c630a2d6925` — document watchdog alert resolution acceptance

### Tests / checks / results

- Re-fetched the committed acceptance script and manually inspected the final recovery sequence and parser boundary.
- Ran credential-free parser micro-checks locally for empty/resolved, title match, summary match, unrelated alerts, invalid root shapes, malformed entries: PASS.
- The repository checkout/Docker environment is still unavailable to this run, so the exact committed unittest module and Docker Compose acceptance could not be executed end-to-end. No green-suite claim is made.
- No GitHub Actions workflow was created, modified, triggered, or rerun.
- No external Grafana, Grafana Cloud, GCP, IAM, Cloud Run, Secret Manager, Gemini, checkpoint, or remediation resource was changed.

### Decisions

1. Recovery is an observable contract, not cleanup: the acceptance rehearsal must prove both Prometheus recovery ingestion and Grafana alert resolution.
2. A malformed Grafana active-alert response fails closed and cannot count as resolution.
3. Alert resolution is scoped to the StageGuard watchdog rule; unrelated alerts may legitimately remain active.
4. The acceptance utility remains loopback-only because it uses local-development Grafana credentials.
5. No CI is triggered merely to obtain test signal while direct repository execution remains unavailable.

### Blockers / unknowns

- The new exact unittest module still needs execution from a runnable checkout.
- The Docker acceptance rehearsal still needs a real local stack run against the currently pinned Grafana image to verify firing and resolution timing/API shape together.
- The authenticated metrics bridge still needs one disposable-project acceptance against a private Cloud Run StageGuard service with a least-privilege invoker identity.
- Cloud Storage Policy Troubleshooter and live Gemini/Vertex acceptance still require authorized disposable-project credentials.

## Single best next step

**On the first runnable Docker checkout, run the focused observability unit tests and `python runtime/watchdog_observability_acceptance.py` against the default Compose stack. If that passes, move to the next production gap: add scrape-freshness/staleness observability so StageGuard can distinguish a healthy `deadline_exceeded=0` sample from a metrics pipeline that has silently stopped delivering fresh runtime telemetry.**

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from last executable run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively; it predates the new watchdog fixture/acceptance path.
- Official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`.
- Incident flow baseline: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.
