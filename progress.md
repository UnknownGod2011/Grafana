# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the indispensable runtime evidence plane. The working vertical slice remains: deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, restart reconciliation, and a same-origin operator cockpit.

Core invariants:
- Grafana is the evidence plane; infrastructure write credentials stay isolated from Grafana/MCP access.
- Gemini is optional/advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact evidence revision.
- Remediation success is never inferred from an action response; fresh Grafana telemetry must prove recovery.
- Authenticated checkpoints and audit integrity fail closed.

## Run log — 2026-09-10 — authenticated runtime metrics ingestion + local watchdog rehearsal

### Inspected at start

Read `progress.md` completely before deciding work. Inspected the runtime observability/auth path and relevant source-controlled artifacts:
- `docker-compose.yml`
- `runtime/prometheus.yml`
- `runtime/api.py` (`/metrics`, `/readyz`, watchdog metric export and lifecycle auth boundary)
- `runtime/Dockerfile`
- `Dockerfile.api`
- `runtime/requirements-cloudrun.txt`
- `runtime/grafana/provisioning/alerting/stageguard-watchdog.yml`
- `runtime/tests/test_grafana_runtime_observability.py`
- `runtime/README.md`
- repository tree and current main-branch head

Confirmed the previous run had created the runtime watchdog dashboard and Grafana-managed alert, but local Prometheus still scraped only the broadcast simulator. The watchdog dashboard therefore had no local runtime-series source. Also confirmed the app-level `/metrics` endpoint itself is intentionally non-secret, while an authenticated Cloud Run deployment still protects the entire service at the platform/IAM boundary; scraping production metrics must not require making Cloud Run public.

### Research / attribution

Checked current official documentation before implementing the production path:
- Google Cloud Run service-to-service authentication / ID-token flow: https://cloud.google.com/run/docs/authenticating/service-to-service
- Google Cloud ID token guidance: https://cloud.google.com/docs/authentication/get-id-token
- Prometheus scrape/auth configuration: https://prometheus.io/docs/prometheus/latest/configuration/configuration/
- Grafana Alerting provisioning / Alertmanager behavior: https://grafana.com/docs/grafana/latest/alerting/set-up/provision-alerting-resources/

The implementation follows Google Cloud's documented pattern of obtaining a short-lived ID token for the target Cloud Run audience through Application Default Credentials. No third-party bridge implementation was copied.

### Exact changes made

Added `runtime/cloud_run_metrics_bridge.py`:
1. Adds a narrow identity-aware scrape bridge for authenticated StageGuard Cloud Run deployments.
2. Accepts one HTTPS StageGuard service origin and derives only `/metrics`; user info, arbitrary paths, queries, fragments, untrimmed input, and non-HTTPS targets are rejected.
3. Obtains a short-lived Google-signed ID token through `google-auth` / Application Default Credentials. `google-auth` was already present in the production dependency set.
4. Owns the upstream `Authorization` header and never forwards scrape-client headers.
5. Bounds the upstream metrics response to 2 MiB and request duration to a configured positive timeout.
6. Returns sanitized `502 stageguard metrics upstream unavailable` on token/upstream failures; exception text, ADC detail, target URL, provider response body, and token material are not returned.
7. Exposes only local `/metrics` and `/healthz`; it is not an arbitrary reverse proxy.
8. Binds loopback by default. Non-loopback binding requires explicit `--allow-network-bind`, intended only for a trusted private container/VPC network.
9. Supports `STAGEGUARD_METRICS_TARGET` and an optional explicit `STAGEGUARD_METRICS_AUDIENCE` for deployments with a custom accepted audience.

Added `runtime/watchdog_metrics_fixture.py`:
1. Adds a credential-free, metrics-only local watchdog fixture.
2. Exposes exactly the four dashboard/alert series: execution active, age, maximum duration, and deadline exceeded.
3. Provides only three deterministic states: `idle`, `active`, and `overdue`.
4. The control surface is limited to `/scenario/{idle|active|overdue}`; it has no remediation provider, incident lifecycle, arbitrary target, token, action, or execution endpoint.
5. Uses a lock around fixture state so concurrent Prometheus scrapes and scenario transitions remain deterministic.

Updated `runtime/Dockerfile`:
- packages the watchdog fixture beside the existing simulator and exposes the internal fixture port.

Updated `docker-compose.yml`:
1. Adds the `watchdog-fixture` service using the existing tiny local runtime image.
2. Publishes the fixture on host loopback only: `127.0.0.1:9111:9111`.
3. Adds a health check and makes Prometheus wait for both simulator and fixture health.
4. Does not start Gemini/MCP or any remediation provider as a side effect.

Updated `runtime/prometheus.yml`:
- adds `stageguard-runtime-watchdog` scraping `watchdog-fixture:9111` with fixed `environment=demo` and `component=stageguard-runtime` labels.
- leaves the existing broadcast simulator scrape intact.
- documents that production should use the authenticated Cloud Run bridge or an equivalent trusted identity-aware collector rather than make Cloud Run public.

Added `runtime/watchdog_observability_acceptance.py`:
1. Drives only the local watchdog fixture.
2. Starts from `idle` and waits for Prometheus to ingest `deadline_exceeded=0`.
3. Moves to `overdue` and waits for Prometheus to ingest `1`.
4. Queries Grafana's Alertmanager API and waits for the source-controlled watchdog rule to become active.
5. Always attempts to reset the fixture to `idle` in `finally`.
6. Requires fixture, Prometheus, and Grafana endpoints to be loopback HTTP service origins before doing anything, preventing the repository's local default Grafana credentials from being sent to a remote host by mistake.

Added `docs/runtime-metrics-ingestion.md`:
- documents local fixture rehearsal and the acceptance command;
- documents the authenticated Cloud Run ID-token bridge and Prometheus scrape topology;
- requires `roles/run.invoker` (or equivalent least privilege) for the bridge workload identity;
- recommends attached service identity on Google Cloud and Workload Identity Federation outside Google Cloud instead of long-lived service-account keys;
- explains the Grafana Cloud/remote-Prometheus trust split and explicitly does not embed tenant IDs, backend URLs, tokens, notification destinations, or Cloud Run invoker credentials.

Added / updated regression coverage:
- `runtime/tests/test_cloud_run_metrics_bridge.py` verifies HTTPS-origin restriction, audience restriction, bridge-owned Authorization, non-loopback opt-in, and sanitized upstream failure behavior.
- `runtime/tests/test_watchdog_metrics_fixture.py` verifies exact idle/active/overdue metric values, rejects unknown state, and exercises the bounded HTTP control surface.
- `runtime/tests/test_grafana_runtime_observability.py` now verifies Compose packages/starts the fixture, host publishing is loopback-only, and Prometheus actually has a runtime-watchdog scrape target feeding the existing Grafana datasource.

Commits this run:
- `bf2b571aafed8691f706ef79735789bb663b65ce` — add authenticated Cloud Run metrics bridge
- `b35d86997192891224474f6d21afa551f8d4885e` — add local watchdog metrics fixture
- `3d71c6038ca22623f94aae9d66e04c8190ac54e8` — add bridge safety tests
- `35b1d4f83cd5bcbce8c8cc65e675fb7c548fa609` — package watchdog fixture in local runtime image
- `adcd836460afebeac70b63294fe92ae93f1b9351` — wire watchdog fixture into Docker Compose
- `fd0f70a8dd086c51c449b55729539d372456a440` — ingest local runtime watchdog metrics in Prometheus
- `35b7785925153d25ad0966b1599851c8e80ba341` — test watchdog metrics rehearsal fixture
- `5a7aae4dd28ef6e9934ff29600baefd240803b9a` — correct explicit HTTP-error import in bridge regression
- `c14c08e1670ad074bba7179a0d52f2304c499621` — document authenticated runtime metrics ingestion
- `86e59920d6289b8535c476b4cdcaef279b837038` — cover local watchdog ingestion contract
- `035c030957c5a633836ba76a1b815ebe90781df1` — add local Grafana watchdog acceptance rehearsal
- `75c70eb293751b315a158c993ba9d18fa80d1311` — keep acceptance endpoints loopback-only
- `7af88871b000e6eb58c7fbd901a574698df4f8fe` — document watchdog observability acceptance command

### Tests / checks / results

Validation performed:
- Re-fetched `runtime/cloud_run_metrics_bridge.py` from the committed main branch and inspected the final target/audience validation, token injection, bounded response, sanitized failure path, and explicit network-bind guard.
- Re-fetched the Grafana alerting rule and confirmed the acceptance script targets the committed alert title/summary and the rule still evaluates `max(stageguard_remediation_execution_deadline_exceeded)` with `for: 10s`.
- Re-fetched the updated local ingestion documentation and checked its commands against the committed fixture/bridge ports and arguments.
- Attempted a fresh checkout and focused test run:
  `python -m unittest runtime.tests.test_cloud_run_metrics_bridge runtime.tests.test_watchdog_metrics_fixture runtime.tests.test_grafana_runtime_observability -v`
- The execution container still failed before checkout with `Could not resolve host: github.com`. No executable green-suite claim is made.
- Did not create, trigger, rerun, or modify any GitHub Actions workflow.

No real Grafana Cloud stack, Grafana notification route, Cloud Run service, Google Cloud project, IAM policy, Secret Manager secret, Gemini endpoint, checkpoint object, or remediation endpoint was modified.

### Decisions made

1. Production metrics ingestion must preserve authenticated Cloud Run. The bridge authenticates *toward* Cloud Run rather than weakening Cloud Run/IAP/IAM to accommodate Prometheus.
2. The bridge is a fixed-purpose `/metrics` fetcher, not a generic authenticated proxy. Arbitrary upstream paths and forwarded caller headers are intentionally impossible.
3. No static ID token is stored in Prometheus YAML. The bridge obtains short-lived tokens from ADC on demand.
4. The local watchdog fixture models observability state only. It cannot perform or emulate remediation actions, preventing a demo helper from accidentally becoming another write path.
5. The fixture is enabled in the default local Compose stack because the runtime-safety dashboard otherwise has no meaningful local data source. Its only host port is loopback-bound.
6. The acceptance utility is deliberately local-only because it uses known local Grafana development credentials. Remote observability acceptance should use deployment-specific credentials and tooling rather than repurpose this script.
7. Grafana Cloud/backend secrets and Cloud Run invoker credentials remain deployment-owned; none are committed.
8. No CI was used merely to compensate for the automation container's DNS failure.

### Current blockers / unknowns

- The new bridge, fixture, observability contract tests, and Docker acceptance utility still need execution from a runnable checkout/Docker host.
- The exact Grafana Alertmanager active-alert response shape should be confirmed against the repository's currently pulled `grafana/grafana:latest` image during the first runnable Docker acceptance. The script accepts either the committed alert title label or committed summary annotation to reduce version-shape brittleness.
- The authenticated bridge still needs one authorized disposable-project acceptance against a private Cloud Run StageGuard deployment using an attached service account with `roles/run.invoker`.
- A production Grafana Cloud remote-write example remains intentionally abstract until an operator chooses a concrete Grafana Cloud stack/tenant; no repository secret or tenant identity should be invented.
- The exact Cloud Storage object Policy Troubleshooter tuple still needs one authorized disposable-project acceptance run.
- Gemini deployment doctor and real Vertex AI acceptance smoke still need authorized disposable-project credentials.

## Single best next step

**Run and harden the new local observability acceptance path on a Docker-capable checkout: execute `python runtime/watchdog_observability_acceptance.py`, confirm the Grafana v13-compatible Alertmanager API exposes the firing rule as expected, then make the acceptance script also prove the alert resolves after it resets the fixture to `idle`. If the current Grafana API shape differs, adapt the parser against the live self-managed response without weakening the alert semantics.**

## Retained production hardening

- Cloud Run production deployment uses authenticated GCS checkpoints rather than silent ephemeral/no-checkpoint state.
- Runtime checkpoint HMAC keys are Secret Manager supplied and at least 32 UTF-8 bytes.
- Checkpoint object validation is byte-accurate and aligned across deploy helper, deployment doctor, and runtime.
- Cloud Run deployment rejects malformed/injected comma-delimited environment and secret mapping inputs before `gcloud`.
- Google Cloud project/region/service/image identifier grammar is centralized and shared by the deploy helper and deployment doctor.
- Live deployment preflight verifies the configured Cloud Run region against the current provider-reported region catalog.
- Runtime MCP launcher parsing is centralized and cross-platform.
- Readiness validates local activation/pin trust before spawning/querying Grafana MCP.
- Deployment-doctor gcloud process failures fail closed with probe-specific sanitized diagnostics.
- Production remediation releases the lifecycle lock across provider contact and Grafana recovery polling while blocking competing mutations with an explicit in-flight guard.
- HTTP concurrency coverage protects incident/readiness/metrics visibility and single-dispatch semantics while remediation is active.
- Active remediation has a monotonic bounded watchdog; exceeding it withdraws readiness without replaying or cancelling the action.
- Watchdog state is exported through authenticated lifecycle state, explicit readiness, and fixed-cardinality Prometheus gauges.
- The watchdog duration is configurable through runtime bootstrap, validated Cloud Run process configuration, and the safe deployment helper.
- Grafana has a source-controlled runtime-safety dashboard and critical remediation deadline alert.
- Local Prometheus now receives deterministic watchdog runtime series for dashboard/alert rehearsal.
- Production Cloud Run metrics can be scraped through a narrow ID-token bridge without making the service public.
- Gemini acceptance smoke defaults to zero model calls and requires explicit `--execute`.
- Standard Cloud Run deployment keeps production remediation disabled.

## Validation baseline retained

- Local onboarding doctor: 8 tests passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable run: 81/81 passed.
- Historical full suite baseline: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Live Docker rehearsal: PASS twice consecutively (historical baseline; does not include this run's new watchdog fixture/acceptance utility).
- Official Grafana MCP read-only smoke path: PASS using `grafana/mcp-grafana:1.3.0`.
- Incident flow: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.
