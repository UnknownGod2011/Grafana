# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence plane. The current vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, restart reconciliation, operator UI, production deployment hardening, runtime watchdog observability, authenticated Cloud Run metrics ingestion, explicit stale-telemetry detection, and a credential-free metrics-outage rehearsal path.

Core invariants remain unchanged:
- Grafana/MCP is read-only evidence access; infrastructure write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Approval is exact-revision-bound and single-use.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove it.
- Durable checkpoint/audit integrity failures fail closed.
- A healthy watchdog value is trustworthy only while the observability path is delivering fresh samples.
- Loss of observability must never be reclassified as a positive remediation deadline breach.

## Run log — 2026-09-11 — stale telemetry end-to-end rehearsal

### Inspected at start

Read `progress.md` completely before making changes. Then inspected the current repository and specifically:
- `runtime/watchdog_metrics_fixture.py`
- `runtime/watchdog_observability_acceptance.py`
- `runtime/tests/test_watchdog_metrics_fixture.py`
- `runtime/tests/test_watchdog_observability_acceptance.py`
- `runtime/grafana/provisioning/alerting/stageguard-watchdog.yml`
- `docker-compose.yml`
- `runtime/Dockerfile`
- `docs/runtime-metrics-ingestion.md`

The previous handoff's gap was confirmed: the fixture could change watchdog values but could not independently break metrics delivery, so the stale-telemetry alert could not yet be rehearsed without conflating evidence loss with remediation state.

### Exact changes made

#### Independent telemetry outage injection

Updated `runtime/watchdog_metrics_fixture.py` so telemetry availability is independent of the existing `idle`, `active`, and `overdue` remediation/watchdog states.

New bounded control endpoints:
- `POST /telemetry/offline`
- `POST /telemetry/online`

Behavior:
- offline mode makes only `GET /metrics` return HTTP 503;
- `/healthz`, `/state`, and the control surface remain reachable;
- the currently selected remediation/watchdog state is preserved while metrics are offline;
- `/state` now exposes `telemetry_available` so tests can prove this separation directly;
- the telemetry control accepts only the two fixed modes and adds no provider/remediation capability.

The state object also rejects non-boolean telemetry availability internally.

#### Full stale-evidence acceptance lifecycle

Expanded `runtime/watchdog_observability_acceptance.py` from a single deadline-alert rehearsal into two independent safety proofs.

The existing deadline path still proves:
`idle -> overdue -> critical alert active -> idle -> critical alert resolved`

The new metrics-outage path proves:
`fresh healthy sample -> /metrics unavailable -> Prometheus sample age >45s -> stale warning active -> metrics restored -> fresh sample -> stale warning resolved`

Critical safety assertions during the outage:
- remediation state remains `idle`;
- the critical remediation-deadline alert must remain inactive before and while the stale warning is active;
- Prometheus must directly show the freshness expression crossing the 45-second threshold;
- after telemetry resumes, freshness must fall back below 45 seconds;
- the stale warning must resolve;
- the critical deadline alert must still remain inactive after evidence recovery.

The acceptance script now gives the two Grafana rules separate title/summary identities instead of treating every StageGuard alert as the deadline rule. Unexpected active-alert API shapes continue to fail closed.

Added `--stale-timeout` with a 95-second default so the bounded rehearsal has enough room for the 45-second sample-age threshold plus the stale rule's 30-second pending period and Grafana's evaluation interval.

All timeout arguments are now validated as finite positive numbers; zero, negative, boolean, NaN, and infinities fail before network work begins.

The `finally` path restores both telemetry online and remediation/watchdog state to idle.

#### Regression coverage

Expanded `runtime/tests/test_watchdog_metrics_fixture.py` to cover:
- telemetry availability remaining independent of active remediation state;
- `/metrics` returning 503 while `/state` still reports the unchanged active state;
- telemetry restoration resuming the same state's metrics;
- rejection of non-boolean telemetry availability;
- existing bounded scenario controls remaining intact.

Expanded `runtime/tests/test_watchdog_observability_acceptance.py` to cover:
- separate deadline and stale-alert identities;
- stale alerts not being mistaken for deadline alerts;
- the freshness PromQL contract containing both `timestamp(...)` and `absent(...)` branches;
- the fixed 45-second freshness threshold;
- telemetry-mode type validation before HTTP work;
- finite-positive timeout validation;
- existing loopback-only URL protections and malformed Grafana response fail-closed behavior.

#### Documentation

Updated `docs/runtime-metrics-ingestion.md` with:
- the new `/telemetry/offline` and `/telemetry/online` controls;
- the explicit statement that metrics failure does not change remediation state;
- the complete two-alert acceptance lifecycle;
- the requirement that the critical deadline alert remain inactive during stale evidence;
- recovery requirements for Prometheus freshness and Grafana alert resolution;
- the bounded `--stale-timeout` behavior.

### Commits this run

- `d350f5261800d6f27bab41c32ebef4db71f9a04c` — add watchdog telemetry outage injection
- `cf493de7cb4053c810ac8a06c1e144e980f5aa75` — test independent watchdog telemetry outage
- `57d144a0cb318dd59c77a1cfdb320dc9e3b7b6a9` — rehearse stale watchdog telemetry lifecycle
- `db3808a239ecb23916987eb1daae0c231c2d8477` — test stale telemetry acceptance helpers
- `5070bcbad3e71132b8a566c0541d0fc56900200a` — document stale telemetry outage rehearsal
- `f093e2dea1d011be49411e926d0b349f0b69e93d` — fail closed on invalid watchdog rehearsal timeouts
- `2567a3c6e844bdaa2cc0170e15167a94126d5ae0` — cover bounded rehearsal timeout validation

### Tests / checks / results

- Re-fetched and inspected the committed `runtime/watchdog_metrics_fixture.py`; the telemetry switch is independent from remediation state and only `/metrics` becomes unavailable.
- Re-fetched and inspected the committed `runtime/watchdog_observability_acceptance.py`; deadline and stale-alert identities, freshness threshold checks, false-critical-alert guards, recovery checks, cleanup, and finite-positive timeout validation are present.
- Confirmed `docker-compose.yml` already builds the fixture from `runtime/` and publishes port 9111 loopback-only, and `runtime/Dockerfile` already copies `watchdog_metrics_fixture.py`; no Compose/Dockerfile mutation was needed for the new outage control.
- Attempted a fresh checkout and focused run with `python -m unittest runtime.tests.test_watchdog_metrics_fixture runtime.tests.test_watchdog_observability_acceptance`. The environment again failed before checkout because `github.com` DNS resolution is unavailable (`Could not resolve host: github.com`). The committed unit tests and Docker acceptance are therefore not claimed green.
- No GitHub Actions workflow was created, modified, triggered, or rerun.
- No external Grafana, Grafana Cloud, GCP, IAM, Cloud Run, Secret Manager, Gemini, checkpoint, or remediation resource was changed.

### Decisions

1. Telemetry outage is modeled as transport/evidence failure, not as another remediation scenario. This prevents tests from accidentally coupling observability health to incident state.
2. The fixture returns HTTP 503 instead of stale synthetic metrics. Prometheus therefore exercises its real failed-scrape/sample-aging behavior.
3. The acceptance explicitly checks the critical deadline rule remains inactive during stale evidence; a stale warning alone is not sufficient proof because a rule-wiring bug could otherwise fire both.
4. Recovery requires both data-plane freshness and alert-plane resolution. Merely making `/metrics` return 200 again is insufficient.
5. Failure-injection controls remain local, fixed-purpose, credential-free, and incapable of performing remediation.
6. Acceptance timeouts fail closed on non-finite values so `NaN`/infinite command-line values cannot accidentally create unbounded or nonsensical waits.

### Blockers / unknowns

- The focused unit tests still need execution from a runnable checkout.
- The full Docker rehearsal now needs to run against the committed Prometheus/Grafana images to confirm actual sample aging, the 30-second pending interval, active-alert API behavior, and warning resolution.
- `docker-compose.yml` currently uses `prom/prometheus:latest` and `grafana/grafana:latest`; this makes the local acceptance environment non-reproducible and permits upstream API/config drift between runs.
- The authenticated metrics bridge still needs one disposable-project acceptance against a private Cloud Run StageGuard service with a least-privilege invoker identity.
- Cloud Storage Policy Troubleshooter and live Gemini/Vertex acceptance still require authorized disposable-project credentials.

## Single best next step

**Make the local observability rehearsal reproducible: replace the `latest` Prometheus and Grafana Compose tags with explicitly documented, current stable versions/digests after checking official release sources, add a lightweight configuration/contract test for those pins, and then run the complete deadline + telemetry-outage acceptance on the first environment where Docker and repository checkout are available. This prevents upstream `latest` drift from invalidating the Grafana Alertmanager and PromQL behavior StageGuard now depends on.**

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from last executable run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively; it predates the new watchdog freshness acceptance path.
- Official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`.
- Incident flow baseline: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.
