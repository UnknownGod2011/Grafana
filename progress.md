# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence plane. The current vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, restart reconciliation, operator UI, production deployment hardening, runtime watchdog observability, authenticated Cloud Run metrics ingestion, and explicit stale-telemetry detection.

Core invariants remain unchanged:
- Grafana/MCP is read-only evidence access; infrastructure write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Approval is exact-revision-bound and single-use.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove it.
- Durable checkpoint/audit integrity failures fail closed.
- A healthy watchdog value is trustworthy only while the observability path is delivering fresh samples.

## Run log — 2026-09-11 — watchdog telemetry freshness

### Inspected at start

Read `progress.md` completely first. Then inspected the current runtime tree and specifically:
- `runtime/grafana/provisioning/alerting/stageguard-watchdog.yml`
- `runtime/grafana/dashboards/stageguard-runtime.json`
- `runtime/tests/test_grafana_runtime_observability.py`
- `runtime/prometheus.yml`
- `runtime/watchdog_metrics_fixture.py`
- `docs/runtime-metrics-ingestion.md`

The prior run's next production gap was confirmed: StageGuard could display `stageguard_remediation_execution_deadline_exceeded=0` even when that sample was old because the scrape/bridge path had stopped delivering telemetry. The watchdog value and telemetry freshness therefore needed to become separate observable conditions.

### Research / attribution

Checked current official documentation before selecting the PromQL contract:
- Prometheus query functions (`time`, `timestamp`, `absent`): https://prometheus.io/docs/prometheus/latest/querying/functions/
- Grafana Prometheus alerting guidance, including missing/stale series patterns: https://grafana.com/docs/grafana/latest/datasources/prometheus/alerting/

Prometheus documents `time()` as query evaluation time and `timestamp()` as each sample's timestamp. Grafana documents `absent()` / `absent_over_time()` patterns for metrics that stop arriving. No third-party implementation code was copied.

### Exact changes made

#### Separate stale-evidence alert

Updated `runtime/grafana/provisioning/alerting/stageguard-watchdog.yml` with a second Grafana-managed rule:

`stageguard-runtime-telemetry-stale`

Its PromQL is:

```promql
max(time() - timestamp(stageguard_remediation_execution_deadline_exceeded))
or vector(1000000000) * absent(stageguard_remediation_execution_deadline_exceeded)
```

Behavior:
- sample age greater than 45 seconds is stale;
- the condition must persist for 30 seconds before warning;
- a completely absent series maps to a deliberately huge sample age so missing telemetry follows the same stale-evidence path;
- the alert is `warning`, separate from the `critical` remediation-deadline alert;
- the description explicitly forbids inferring remediation safety from an old zero value;
- no remediation, notification destination, credential, or provider detail is introduced.

The existing `stageguard-remediation-deadline` rule is unchanged semantically and still uses `NoData` instead of pretending missing data is a deadline breach.

#### Grafana freshness panel

Updated `runtime/grafana/dashboards/stageguard-runtime.json` to dashboard version 2 and added panel ID 5, `Watchdog telemetry freshness`.

The panel displays the age of the newest watchdog deadline sample using the same PromQL as the stale alert, with visual thresholds at 30 seconds and 45 seconds. This means operators can distinguish:
- fresh `deadline_exceeded=0` -> watchdog is healthy and evidence is current;
- fresh `deadline_exceeded=1` -> remediation execution deadline breached;
- stale/missing sample -> watchdog health is unknown regardless of the last stored value.

#### Regression coverage

Expanded `runtime/tests/test_grafana_runtime_observability.py` to assert:
- the freshness expression is present in the dashboard;
- panel ID 5 is the dedicated freshness panel;
- the stale rule has its own stable UID;
- the stale threshold is 45 seconds with a 30-second pending duration;
- the stale alert is bound to panel 5 and severity `warning`;
- the query contains both `timestamp(...)` and `absent(...)` fail-safe branches;
- the original deadline rule still treats missing telemetry as `NoData` rather than conflating it with a real execution breach;
- alert provisioning still contains no notification destinations or secrets.

#### Documentation

Updated `docs/runtime-metrics-ingestion.md` with a dedicated freshness section explaining the two independent safety conditions, the exact PromQL, thresholds, absent-series behavior, and current official Prometheus/Grafana references.

### Commits this run

- `0aa30ffd891278dadd35c23320451c4971dcd2eb` — alert on stale StageGuard watchdog telemetry
- `91eca870c74635c7842e9465fabcee93502cce14` — show watchdog telemetry freshness in Grafana
- `330658ebce26cfe9eb9da2a8ec9839d0c78a71eb` — test watchdog telemetry freshness observability
- `5a80c97da6885bdfe1dd4163e96c0d51b9a0e280` — document watchdog telemetry freshness contract

### Tests / checks / results

- Re-fetched and inspected the committed Grafana alerting YAML after the write: the original deadline rule and new stale-evidence rule are both present with separate UIDs, severities, panel bindings, and meanings.
- Re-fetched and inspected the committed dashboard JSON after the write: panel ID 5 is present, uses the provisioned Prometheus datasource, and carries the exact freshness expression.
- Attempted a clean checkout plus `python -m unittest runtime.tests.test_grafana_runtime_observability`; the execution environment still failed before checkout because `github.com` DNS resolution is unavailable. Therefore the exact committed unittest is not claimed green.
- No GitHub Actions workflow was created, modified, triggered, or rerun.
- No external Grafana, Grafana Cloud, GCP, IAM, Cloud Run, Secret Manager, Gemini, checkpoint, or remediation resource was changed.

### Decisions

1. Deadline state and evidence freshness are intentionally separate alerts. Missing telemetry must not be mislabeled as a confirmed remediation deadline breach.
2. Freshness is derived from Prometheus sample timestamps instead of adding a second runtime-generated clock metric, keeping the application/runtime API surface smaller and measuring the actual ingestion path.
3. A missing series is treated as stale evidence rather than healthy or silently `NoData` for the freshness rule.
4. The 45-second threshold is deliberately much larger than the local 2-second scrape interval, leaving room for transient scrape jitter while still surfacing a broken evidence path promptly.
5. The alert remains observational only; Grafana continues to have no remediation credentials or action authority.

### Blockers / unknowns

- The focused observability unittest still needs execution from a runnable checkout.
- The Docker rehearsal still needs to exercise an intentionally interrupted watchdog scrape so the new stale alert can be proven firing and resolving against the pinned Grafana/Prometheus images.
- The authenticated metrics bridge still needs one disposable-project acceptance against a private Cloud Run StageGuard service with a least-privilege invoker identity.
- Cloud Storage Policy Troubleshooter and live Gemini/Vertex acceptance still require authorized disposable-project credentials.

## Single best next step

**Extend the credential-free watchdog fixture and acceptance rehearsal with a bounded `telemetry-offline` mode that makes `/metrics` unavailable without changing remediation state. Prove end-to-end that Prometheus sample age crosses the freshness threshold, Grafana fires `stageguard-runtime-telemetry-stale`, the critical deadline alert does not falsely fire, and both telemetry freshness and the warning alert recover after scraping resumes.**

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from last executable run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively; it predates the new watchdog freshness acceptance path.
- Official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`.
- Incident flow baseline: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.
