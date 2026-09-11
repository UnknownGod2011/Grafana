# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence plane. The current vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, restart reconciliation, operator UI, production deployment hardening, runtime watchdog observability, authenticated Cloud Run metrics ingestion, stale-telemetry detection, a credential-free metrics-outage rehearsal path, pinned Grafana/Prometheus acceptance images, live runtime-version attestation, strict Prometheus safety-query parsing, a live query-local cardinality ambiguity probe, separate liveness/readiness semantics for the private Cloud Run metrics bridge, and an explicit Prometheus scrape-health warning for the runtime watchdog target.

Core invariants:
- Grafana/MCP is read-only evidence access; infrastructure write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Approval is exact-revision-bound and single-use.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove it.
- Durable checkpoint/audit integrity failures fail closed.
- A healthy watchdog value is trustworthy only while the observability path is delivering fresh samples.
- Loss of observability must never be reclassified as a positive remediation deadline breach.
- Ambiguous, malformed, or non-finite Prometheus safety evidence must never be interpreted as a healthy acceptance signal.
- Metrics bridge process liveness must not be confused with authenticated upstream readiness.
- Prometheus scrape failure is a transport/collection warning, not evidence that a remediation deadline was exceeded.

## Run log — 2026-09-11 — explicit watchdog scrape-health observability

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected the repository through the GitHub connector, including:
- `docker-compose.yml`
- `runtime/prometheus.yml`
- `runtime/grafana/provisioning/alerting/stageguard-watchdog.yml`
- `runtime/grafana/dashboards/stageguard-runtime.json`
- `runtime/watchdog_observability_acceptance.py`
- current runtime test layout.

Also attempted a fresh local checkout:

```bash
git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard
```

The execution container still failed with `Could not resolve host: github.com`, so committed tests and the Docker rehearsal could not execute locally in this run. Work continued through the GitHub repository API instead of stopping on the transient environment limitation.

### Problem identified

StageGuard already had a fail-safe stale-sample alert for the watchdog safety metric, but operators had no fast, explicit signal that Prometheus itself was currently unable to scrape the watchdog target. A metrics bridge/IAM/network/service failure therefore had to age into the 45-second freshness threshold before the dashboard explained that the evidence path was broken.

The desired model is three distinct signals:
1. `up{job="stageguard-runtime-watchdog"}` — transport/scrape health;
2. watchdog sample age — whether prior runtime-safety evidence is still fresh enough to trust;
3. `stageguard_remediation_execution_deadline_exceeded` — positive evidence of an actual remediation deadline breach.

These signals must not be conflated.

### Exact changes made

#### Added a Grafana-managed watchdog scrape-failure warning

Updated `runtime/grafana/provisioning/alerting/stageguard-watchdog.yml` with rule `stageguard-runtime-scrape-down`:
- query: `max(up{job="stageguard-runtime-watchdog"})`;
- alert condition: value below `0.5`;
- `for: 20s` to avoid a single transient scrape producing operator noise;
- `noDataState: Alerting` so a missing target-health series cannot be interpreted as healthy;
- severity remains `warning`, separate from the `critical` remediation deadline rule;
- the annotation explicitly says scrape failure does **not** mean a remediation deadline was exceeded;
- links to runtime safety dashboard panel 6.

Commit:
- `072f6a97bd927d2b53f1429fe686e71b574cc6b5` — add watchdog scrape health alert

#### Added dashboard transport-health visibility

Updated `runtime/grafana/dashboards/stageguard-runtime.json`:
- new panel 6: `Watchdog scrape health`;
- expression: `min(up{job="stageguard-runtime-watchdog"})`;
- maps `1` to healthy and `0` to scrape failing;
- description distinguishes transport failure from positive deadline-breach evidence;
- bumped dashboard version from 2 to 3.

Commit:
- `556696b28b5b2369fdfd85f990bd8af2d00c0b58` — show watchdog scrape health in runtime dashboard

#### Added dependency-free regression contract

Created `runtime/tests/test_watchdog_scrape_health.py` covering:
- stable Prometheus watchdog job name/fixture target;
- presence and identity of the new Grafana-managed alert;
- exact `up{job="stageguard-runtime-watchdog"}` query contract;
- fail-closed `NoData` behavior and 20-second pending window;
- dashboard panel/query binding;
- separation from the remediation deadline metric and stale-telemetry rule.

Commit:
- `de48f6be2871fa9b5dd10f8c14b32f9e5c8ef6aa` — test watchdog scrape health observability contract

#### Documented the three-signal safety model

Created `docs/watchdog-scrape-health.md` explaining:
- scrape health vs sample freshness vs deadline-breach evidence;
- why `up` is useful for fast diagnostics but is not itself the authoritative runtime-safety signal;
- how the local `/telemetry/offline` fixture path can rehearse bridge/target failure without changing remediation state;
- how production Cloud Run deployments should point Prometheus at the authenticated metrics bridge rather than expose StageGuard publicly;
- official Prometheus references for scraping and `job` labeling.

Commit:
- `4abc1ccf48a9465ffca8ff05df6da08dbf4c5300` — document watchdog scrape health signal

### Checks / results

- Re-fetched `stageguard-watchdog.yml` after the write and verified the committed scrape-down rule is present on `main` with the exact `up{job="stageguard-runtime-watchdog"}` selector, fail-closed `NoData`, 20-second pending window, warning severity, and panel 6 binding.
- Confirmed `runtime/prometheus.yml` defines the exact `stageguard-runtime-watchdog` job used by the new rule.
- Consulted current official Prometheus documentation: Prometheus scrapes configured HTTP endpoints and applies the configured `job_name` as the `job` label, which supports the selector used here.
- Local checkout/test execution remained blocked by DNS resolution for `github.com`; no green unittest or Docker claim is made.
- No GitHub Actions workflow was created, modified, triggered, or rerun.
- No external Grafana, Grafana Cloud, GCP, IAM, Cloud Run, Secret Manager, Gemini, checkpoint, or remediation resource was changed.

### Decisions

1. Keep scrape failure and stale evidence as separate warnings. `up == 0` provides fast operational localization; sample age remains the fail-safe evidence-trust boundary.
2. Keep the remediation deadline alert semantically pure. A collection failure must never become a synthetic positive deadline breach.
3. Use the existing Prometheus-generated `up` target-health series rather than adding another application metric or dependency.
4. Alert on missing `up` data as well as explicit zero, because absence of the target-health series is not proof of a healthy collection path.
5. Avoid aggressive single-scrape alerting; require 20 seconds before firing to reduce noise while still warning before the existing stale-sample rule matures.

### Blockers / unknowns

- `runtime/tests/test_watchdog_scrape_health.py` still needs execution from a runnable checkout.
- The complete credential-free Docker watchdog rehearsal still needs to run against pinned Prometheus 3.13.3 and Grafana 13.2.1.
- The live outage rehearsal does not yet assert the new scrape-down alert lifecycle. It should prove the scrape warning fires first, the critical deadline alert stays inactive, the stale-evidence warning later fires, and both warnings resolve after telemetry returns.
- Container digests remain uncommitted because authoritative registry digests have not been verified through the available execution path.
- The authenticated metrics bridge still needs one disposable-project acceptance against a private Cloud Run StageGuard service with a least-privilege invoker identity.

## Single best next step

**Extend `runtime/watchdog_observability_acceptance.py` so the existing `/telemetry/offline` rehearsal explicitly proves the new `stageguard-runtime-scrape-down` alert fires before the stale-evidence alert, confirms the critical remediation-deadline alert remains inactive throughout the outage, and verifies both warnings resolve after telemetry is restored. Then run that acceptance plus `python -m unittest runtime.tests.test_watchdog_scrape_health runtime.tests.test_cloud_run_metrics_bridge runtime.tests.test_watchdog_ambiguity_probe runtime.tests.test_watchdog_observability_acceptance` in the first runnable Docker checkout.**

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from last executable run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively; it predates the newest watchdog freshness acceptance path, explicit image pins, live runtime-version attestation, strict Prometheus safety-query parsing, the live ambiguity probe, bridge readiness work, and the new scrape-health alert.
- Official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`.
- Incident flow baseline: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.
