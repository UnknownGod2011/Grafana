# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence plane. The current vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, restart reconciliation, operator UI, and production deployment hardening.

Core invariants remain unchanged:
- Grafana/MCP is read-only evidence access; infrastructure write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Approval is exact-revision-bound and single-use.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove it.
- Durable checkpoint/audit integrity failures fail closed.

## Run log — 2026-09-10 — authenticated runtime metrics ingestion and watchdog rehearsal

### Inspected at start

Read `progress.md` completely, then inspected `docker-compose.yml`, `runtime/prometheus.yml`, `runtime/api.py`, `runtime/Dockerfile`, `Dockerfile.api`, `runtime/requirements-cloudrun.txt`, the provisioned watchdog alert/dashboard path, observability tests, runtime docs, and repository tree.

The concrete gap was that Grafana had a source-controlled StageGuard watchdog dashboard and alert, but local Prometheus still scraped only the broadcast simulator. Production also needed a secure way for Prometheus-compatible collectors to reach an authenticated Cloud Run `/metrics` endpoint without making the Cloud Run service public.

### Research / attribution

Used current official documentation:
- Google Cloud Run service-to-service authentication: https://cloud.google.com/run/docs/authenticating/service-to-service
- Google Cloud ID tokens: https://cloud.google.com/docs/authentication/get-id-token
- Prometheus scrape/auth configuration: https://prometheus.io/docs/prometheus/latest/configuration/configuration/
- Grafana Alerting provisioning: https://grafana.com/docs/grafana/latest/alerting/set-up/provision-alerting-resources/

The bridge follows Google's documented Application Default Credentials + short-lived ID-token pattern. No third-party implementation was copied.

### Exact changes made

#### Production/private metrics ingestion

Added `runtime/cloud_run_metrics_bridge.py`:
- accepts exactly one trimmed HTTPS service origin and derives only `/metrics`;
- rejects user info, arbitrary paths, query strings, fragments, and non-HTTPS targets;
- obtains a short-lived Google-signed ID token through the already-present `google-auth` production dependency;
- creates its own upstream Authorization header and does not forward caller headers;
- bounds upstream responses to 2 MiB;
- validates scrape timeout as finite and strictly positive, rejecting booleans, zero/negative values, NaN, infinity, and malformed numerics;
- sanitizes upstream/token failures to a generic 502 without returning token, ADC, URL, provider body, or exception details;
- exposes only `/metrics` and `/healthz` and therefore cannot become an arbitrary authenticated proxy;
- binds loopback by default; non-loopback bind requires explicit `--allow-network-bind` for a trusted private network.

#### Credential-free local watchdog ingestion

Added `runtime/watchdog_metrics_fixture.py`:
- emits exactly the four runtime watchdog series consumed by Grafana;
- supports only deterministic `idle`, `active`, and `overdue` states;
- has no remediation/provider/lifecycle/arbitrary-action endpoint;
- protects concurrent state access with a lock.

Updated `runtime/Dockerfile` to package the fixture.

Updated `docker-compose.yml`:
- adds `watchdog-fixture` using the tiny local runtime image;
- exposes it only on `127.0.0.1:9111`;
- adds health checking;
- makes Prometheus wait for both the broadcast simulator and watchdog fixture;
- does not auto-start MCP, Gemini, or remediation.

Updated `runtime/prometheus.yml`:
- adds `stageguard-runtime-watchdog` scraping `watchdog-fixture:9111`;
- uses fixed `environment=demo` and `component=stageguard-runtime` labels;
- preserves the existing simulator scrape.

#### Acceptance tooling

Added `runtime/watchdog_observability_acceptance.py`:
- moves the fixture to idle and waits for Prometheus to observe `deadline_exceeded=0`;
- moves the fixture to overdue and waits for Prometheus to observe `1`;
- waits for the Grafana-managed watchdog alert via Grafana's Alertmanager API;
- resets the fixture to idle in `finally`;
- requires fixture, Prometheus, and Grafana endpoints to be loopback HTTP origins before sending any request, preventing the local default Grafana credentials from being sent remotely by mistake.

Added `docs/runtime-metrics-ingestion.md` describing local rehearsal, the acceptance command, authenticated Cloud Run bridge topology, `roles/run.invoker`, attached workload identity, Workload Identity Federation for off-cloud collectors, and Grafana Cloud/remote Prometheus trust separation. No tenant URL, Grafana token, notification destination, Cloud Run credential, or remediation credential is committed.

#### Tests

Added/updated:
- `runtime/tests/test_cloud_run_metrics_bridge.py` — target/audience restrictions, bridge-owned auth header, finite-positive timeout validation, explicit non-loopback opt-in, sanitized upstream failures;
- `runtime/tests/test_watchdog_metrics_fixture.py` — exact idle/active/overdue series and bounded HTTP control surface;
- `runtime/tests/test_grafana_runtime_observability.py` — Compose packaging/loopback fixture exposure and Prometheus runtime-watchdog scrape contract.

### Commits this run

- `bf2b571aafed8691f706ef79735789bb663b65ce` — authenticated Cloud Run metrics bridge
- `b35d86997192891224474f6d21afa551f8d4885e` — local watchdog metrics fixture
- `3d71c6038ca22623f94aae9d66e04c8190ac54e8` — initial bridge safety tests
- `35b1d4f83cd5bcbce8c8cc65e675fb7c548fa609` — package fixture in local runtime image
- `adcd836460afebeac70b63294fe92ae93f1b9351` — wire fixture into Compose
- `fd0f70a8dd086c51c449b55729539d372456a440` — scrape watchdog fixture from Prometheus
- `35b7785925153d25ad0966b1599851c8e80ba341` — fixture regression tests
- `5a7aae4dd28ef6e9934ff29600baefd240803b9a` — bridge test import correction
- `c14c08e1670ad074bba7179a0d52f2304c499621` — runtime metrics ingestion documentation
- `86e59920d6289b8535c476b4cdcaef279b837038` — local ingestion contract coverage
- `035c030957c5a633836ba76a1b815ebe90781df1` — watchdog observability acceptance tool
- `75c70eb293751b315a158c993ba9d18fa80d1311` — loopback-only acceptance safety
- `7af88871b000e6eb58c7fbd901a574698df4f8fe` — acceptance documentation
- `c3fa473c49c344288711ed4831c89811a1e236cf` — initial run handoff
- `2073e2c6551f0fb3b6dbb392ba336c3cc71d078e` — finite/positive bridge timeout hardening
- `5c78242f9fb4808eaef3afc721a12b175c3e4532` — timeout regression coverage

### Tests / checks / results

- Re-fetched the committed bridge and inspected the final HTTPS-origin boundary, ID-token injection, fixed upstream path, response bound, sanitized failure path, loopback default, and explicit network-bind guard.
- Re-fetched the provisioned Grafana alert and confirmed it still evaluates `max(stageguard_remediation_execution_deadline_exceeded)` with `for: 10s` and `noDataState: NoData`.
- Re-fetched the ingestion documentation and checked commands/ports against the committed files.
- Attempted a fresh checkout and focused run:
  `python -m unittest runtime.tests.test_cloud_run_metrics_bridge runtime.tests.test_watchdog_metrics_fixture runtime.tests.test_grafana_runtime_observability -v`
- The execution container still failed before checkout with `Could not resolve host: github.com`. Therefore no new green-suite claim is made.
- No GitHub Actions workflow was created, modified, triggered, or rerun.
- No external Grafana, Grafana Cloud, GCP, IAM, Cloud Run, Secret Manager, Gemini, checkpoint, or remediation resource was changed.

### Decisions

1. Production metrics ingestion preserves authenticated Cloud Run; observability is not a reason to enable unauthenticated invocation.
2. The bridge is intentionally a fixed-purpose identity-aware `/metrics` fetcher rather than a generic proxy.
3. Prometheus YAML does not contain a static Cloud Run ID token; the bridge obtains short-lived identity from ADC.
4. The local fixture models observability state only and cannot execute remediation.
5. The acceptance utility is local-only because it uses local development Grafana credentials.
6. Missing Grafana watchdog telemetry remains NoData, distinct from a confirmed deadline breach.
7. No CI is used merely to work around this automation environment's DNS limitation.

### Blockers / unknowns

- The new tests and Docker acceptance utility need execution from a runnable checkout/Docker host.
- The exact active-alert response shape from the currently pulled Grafana image should be confirmed during that rehearsal; the acceptance parser currently accepts either the committed alert title label or committed summary annotation.
- The authenticated bridge still needs one disposable-project acceptance against a private Cloud Run StageGuard service using an attached invoker identity.
- Cloud Storage Policy Troubleshooter and live Gemini/Vertex acceptance still require authorized disposable-project credentials.

## Single best next step

**On the first runnable Docker checkout, execute `python runtime/watchdog_observability_acceptance.py`, verify the Grafana Alertmanager response shape, then extend the acceptance utility to prove the watchdog alert resolves after the fixture returns to `idle`. If the current Grafana API shape differs, adapt only the response parser; keep the alert semantics and authentication boundaries unchanged.**

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from last executable run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively; it predates this new fixture/acceptance path.
- Official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`.
- Incident flow baseline: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.
