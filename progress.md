# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence plane. The current vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, restart reconciliation, operator UI, production deployment hardening, runtime watchdog observability, authenticated Cloud Run metrics ingestion, stale-telemetry detection, a credential-free metrics-outage rehearsal path, pinned Grafana/Prometheus acceptance images, live runtime-version attestation, strict Prometheus safety-query parsing, a live query-local cardinality ambiguity probe, separate liveness/readiness semantics for the private Cloud Run metrics bridge, explicit Prometheus scrape-health warning, and an ordered live outage acceptance contract that proves scrape failure is detected before stale evidence while the critical remediation alert remains inactive.

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

## Run log — 2026-09-11 — ordered scrape-failure/stale-evidence acceptance lifecycle

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected the repository through the GitHub connector, including:
- `runtime/watchdog_observability_acceptance.py`
- `runtime/grafana/provisioning/alerting/stageguard-watchdog.yml`
- `runtime/tests/test_watchdog_observability_acceptance.py`
- `docs/watchdog-scrape-health.md`
- the current repository metadata/default branch and retained validation baseline.

The previous run's single best next step was to extend the existing `/telemetry/offline` acceptance path so it proves the new scrape warning fires before the stale-evidence warning, the critical deadline alert stays inactive, and both warnings resolve after recovery.

### Exact changes made

#### Extended the live outage acceptance to cover the scrape-warning lifecycle

Updated `runtime/watchdog_observability_acceptance.py` so the credential-free rehearsal now models three independent observability signals directly:
- positive deadline evidence: `stageguard_remediation_execution_deadline_exceeded`;
- target transport health: `max(up{job="stageguard-runtime-watchdog"})`;
- evidence freshness: the existing timestamp/absent expression.

Added stable scrape-alert identity constants matching the provisioned Grafana rule:
- title: `StageGuard runtime watchdog scrape failing`;
- summary: `Prometheus cannot scrape the StageGuard runtime watchdog target`.

Added `prometheus_scrape_up()` and `scrape_alert_active()` helpers so the acceptance path proves actual Prometheus/Grafana state instead of inferring transport failure from the fixture control endpoint.

The outage lifecycle now requires, in order:
1. watchdog starts healthy with `up == 1` and an idle deadline metric;
2. `/telemetry/offline` is activated without changing remediation state;
3. Prometheus observes `up == 0`;
4. Grafana's scrape-failure warning becomes active within a dedicated bounded timeout;
5. at the moment the scrape warning is first active, the stale warning must still be inactive and the critical deadline alert must be inactive;
6. the watchdog sample ages beyond the 45-second freshness boundary;
7. the stale-evidence warning becomes active while the scrape warning remains active;
8. the critical deadline alert remains inactive throughout the outage;
9. telemetry is restored and Prometheus returns to `up == 1` with fresh healthy deadline evidence;
10. both outage warnings resolve, while the critical deadline alert remains inactive.

Added `--scrape-alert-timeout` (default 50 seconds) and subjected it to the same finite-positive validation as other acceptance timeouts.

Commit:
- `c21689756cb8a2971515adb8ba031a75efa99f27` — extend watchdog outage acceptance with scrape alert lifecycle

#### Added focused regression coverage

Created `runtime/tests/test_watchdog_scrape_lifecycle_acceptance.py` covering:
- exact `stageguard-runtime-watchdog` job/query contract;
- `prometheus_scrape_up()` delegation to the exact target-health query;
- scrape-alert title identity;
- scrape-alert summary identity;
- separation from stale/deadline alert identities;
- fail behavior of the stale-warning ordering guard when stale is already active;
- pass behavior when stale remains inactive during the early scrape-warning phase.

The test is dependency-free and uses `unittest.mock`; it does not require Grafana, Prometheus, Docker, or credentials.

Commit:
- `24c0ec37706d9ce90f0e3767bd32383bdd5778ea` — test watchdog scrape alert acceptance helpers

#### Updated operational documentation

Updated `docs/watchdog-scrape-health.md` with the exact eight-stage operational acceptance contract, including:
- explicit `up == 1 -> 0 -> 1` transitions;
- scrape warning before stale warning;
- simultaneous scrape+stale warnings during a sustained outage;
- critical deadline alert inactivity throughout the transport outage;
- resolution requirements after telemetry recovery;
- rationale for using live Prometheus and Grafana APIs instead of trusting fixture state.

Commit:
- `964aeb83485ab15a941ae22776998a86b1db4810` — document scrape warning lifecycle rehearsal

### Checks / results

- Re-fetched the committed acceptance script after the write and verified on `main`:
  - `SCRAPE_JOB = "stageguard-runtime-watchdog"`;
  - exact `max(up{job="stageguard-runtime-watchdog"})` query;
  - dedicated scrape-alert title/summary;
  - `--scrape-alert-timeout` finite-positive validation;
  - pre-outage `up == 1` assertion;
  - outage `up == 0` assertion;
  - scrape-warning activation before stale-warning activation;
  - critical deadline inactivity checks during the outage;
  - post-recovery `up == 1` assertion;
  - resolution checks for both scrape and stale warnings.
- Re-checked the provisioned Grafana rule and confirmed the acceptance identity/query matches `stageguard-runtime-scrape-down` exactly.
- Attempted a fresh executable checkout and focused unit tests with:

```bash
git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard
python -m unittest \
  runtime.tests.test_watchdog_observability_acceptance \
  runtime.tests.test_watchdog_scrape_health \
  runtime.tests.test_cloud_run_metrics_bridge \
  runtime.tests.test_watchdog_ambiguity_probe
```

The execution container still failed before checkout with `Could not resolve host: github.com`. Therefore no green unittest or Docker claim is made for this run.
- No GitHub Actions workflow was created, modified, triggered, or rerun.
- No external Grafana, Grafana Cloud, GCP, IAM, Cloud Run, Secret Manager, Gemini, checkpoint, or remediation resource was changed.

### Decisions

1. Prove transport state twice: via Prometheus `up` and via Grafana's managed warning. Fixture control state alone is not sufficient acceptance evidence.
2. Treat alert ordering as a safety property. The fast scrape warning should explain collection failure before the slower freshness trust boundary matures.
3. Require the stale warning to still be inactive when the scrape warning first fires. This prevents a configuration regression from silently collapsing the two operational stages.
4. Require the scrape warning to remain active when stale telemetry becomes active. Sustained collection failure should not appear partially recovered.
5. Require both outage warnings to resolve only after Prometheus again reports `up == 1` and fresh watchdog evidence is ingested.
6. Keep the critical deadline alert semantically pure throughout: loss of telemetry remains unknown/degraded evidence, never synthetic proof of an execution deadline breach.

### Blockers / unknowns

- The newly committed regression test still needs execution from a runnable checkout.
- The complete credential-free Docker watchdog rehearsal still needs to run against pinned Prometheus 3.13.3 and Grafana 13.2.1.
- Container digests remain uncommitted because authoritative registry digests have not been verified through the available execution path.
- The authenticated metrics bridge still needs one disposable-project acceptance against a private Cloud Run StageGuard service with a least-privilege invoker identity.
- The historical full-suite failures/errors have not been re-triaged in this run; no full-suite green claim exists.

## Single best next step

**Run the full credential-free pinned Docker rehearsal now that the outage acceptance is complete. It must attest Prometheus 3.13.3 and Grafana 13.2.1, reject the ambiguity probe, prove the deadline alert fires/resolves, then prove `up: 1 -> 0`, scrape warning fires before stale warning, critical deadline remains inactive, stale warning fires, `up: 0 -> 1`, and both outage warnings resolve. In the same runnable checkout execute `python -m unittest runtime.tests.test_watchdog_observability_acceptance runtime.tests.test_watchdog_scrape_health runtime.tests.test_watchdog_scrape_lifecycle_acceptance runtime.tests.test_cloud_run_metrics_bridge runtime.tests.test_watchdog_ambiguity_probe`. If that is green, the next implementation target should shift away from acceptance scaffolding and toward the highest-impact remaining production integration gap (private Cloud Run metrics-bridge acceptance or official Grafana MCP incident-evidence hardening).**

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from last executable run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively; it predates the newest ordered scrape/stale outage acceptance path, explicit image pins, live runtime-version attestation, strict Prometheus safety-query parsing, live ambiguity probe, and bridge readiness work.
- Official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`.
- Incident flow baseline: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.
