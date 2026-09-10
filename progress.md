# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the indispensable runtime evidence plane. The working vertical slice remains: deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, restart reconciliation, and a same-origin operator cockpit.

Core invariants:
- Grafana is the evidence plane; infrastructure write credentials stay isolated from Grafana/MCP access.
- Gemini is optional/advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact evidence revision.
- Remediation success is never inferred from an action response; fresh Grafana telemetry must prove recovery.
- Authenticated checkpoints and audit integrity fail closed.

## Run log — 2026-09-10 — Grafana remediation-watchdog dashboard, alerting, and deploy tuning

### Inspected at start

Read `progress.md` completely before deciding work. Inspected the current Grafana/deployment path and focused regression surface:
- `docker-compose.yml`
- `runtime/prometheus.yml`
- `runtime/grafana/provisioning/datasources/stageguard.yml`
- `runtime/bootstrap_grafana.py`
- `scripts/deploy_cloud_run.sh`
- `runtime/tests/test_cloud_run_deploy_contract.py`
- `runtime/tests/test_cloud_run_deploy_shell.py`
- repository tree under `runtime/grafana/` and `runtime/tests/`

Confirmed the previous run had already exported the four bounded remediation watchdog metrics and wired the duration through bootstrap/Cloud Run entrypoint, but Grafana only provisioned the Prometheus datasource. There was no dashboard provider, no committed dashboard, no alerting provisioning, and the safe Cloud Run deploy helper did not expose the watchdog duration.

### Research / attribution

Checked current official Grafana documentation before implementing the provisioning format:
- Dashboard/data-source provisioning: https://grafana.com/docs/grafana/latest/administration/provisioning/
- Grafana dashboard provisioning tutorial/provider behavior: https://grafana.com/tutorials/provision-dashboards-and-data-sources/
- Grafana Alerting provisioning: https://grafana.com/docs/grafana/latest/alerting/set-up/provision-alerting-resources/
- Alerting provisioning/export format guidance: https://grafana.com/docs/grafana/latest/alerting/set-up/provision-alerting-resources/export-alerting-resources/

The implementation deliberately uses self-managed Grafana file provisioning already supported by the local Docker stack. No third-party dashboard or alert configuration was copied.

### Exact changes made

Added `runtime/grafana/provisioning/dashboards/stageguard.yml`:
1. Adds a source-controlled `StageGuard` file provider.
2. Places the dashboard in the `StageGuard` folder.
3. Reads dashboard JSON from `/var/lib/grafana/dashboards`.
4. Uses `disableDeletion: true` and `allowUiUpdates: false` so the repository remains the source of truth.
5. Uses a 30-second provider update interval, avoiding aggressive polling of a bind-mounted directory.

Added `runtime/grafana/dashboards/stageguard-runtime.json` with stable UID `stageguard-runtime-safety` and four watchdog-focused panels:
- remediation execution active/idle state from `stageguard_remediation_execution_active`;
- high-signal watchdog status from `stageguard_remediation_execution_deadline_exceeded`;
- execution age versus configured maximum from `stageguard_remediation_execution_age_seconds` and `stageguard_remediation_execution_max_seconds`;
- remaining watchdog headroom from `max_seconds - age_seconds`.

All dashboard queries use the existing provisioned `stageguard-prometheus` datasource UID. The dashboard is read-only/source-controlled and refreshes every 5 seconds over a 30-minute default window.

Added `runtime/grafana/provisioning/alerting/stageguard-watchdog.yml`:
1. Adds a Grafana-managed critical rule `stageguard-remediation-deadline` in the `StageGuard` folder.
2. Queries `max(stageguard_remediation_execution_deadline_exceeded)` and evaluates the last value above `0.5`.
3. Uses a 10-second evaluation interval and 10-second pending period.
4. Binds the alert to dashboard UID `stageguard-runtime-safety`, panel 2.
5. Keeps `execErrState: Error`.
6. Uses `noDataState: NoData` rather than treating absent telemetry as a real deadline-exceeded event. This preserves the watchdog alert's semantic signal; missing telemetry is operationally distinct from a confirmed wedged remediation.
7. The annotation explicitly tells operators not to replay remediation and to inspect/reconcile provider state first.
8. Adds no contact point, webhook, notification policy, token, password, or external destination; routing remains an operator deployment choice.

Updated `docker-compose.yml`:
- retained the read-only `/etc/grafana/provisioning` mount;
- added `./runtime/grafana/dashboards:/var/lib/grafana/dashboards:ro`, making the provider's dashboard path concrete in the local stack.

Updated `scripts/deploy_cloud_run.sh`:
1. Added operator control for `STAGEGUARD_REMEDIATION_EXECUTION_MAX_SECONDS` with default `60` only when the variable is unset.
2. Explicitly blank values are rejected instead of silently reverting to the default, matching `cloudrun_entrypoint.py` fail-closed semantics.
3. Rejects zero, negative values, NaN/infinity, whitespace, comma injection, signs/exponent notation, and nonnumeric input before any `gcloud` command.
4. Adds a second finite-positive numeric check through the already-required Python interpreter.
5. Forwards the validated value through Cloud Run `--set-env-vars` as `STAGEGUARD_REMEDIATION_EXECUTION_MAX_SECONDS`.
6. Did not add `STAGEGUARD_ENABLE_REMEDIATION`, a remediation endpoint, token, or reconciliation endpoint. The standard deployment artifact remains write-disabled.

Updated `runtime/tests/test_cloud_run_deploy_contract.py`:
- statically verifies the watchdog setting is validated before `gcloud run deploy`, defaults to 60, is forwarded, and does not introduce remediation enablement.

Updated `runtime/tests/test_cloud_run_deploy_shell.py`:
- removes any inherited watchdog env from the fake-gcloud baseline so default behavior is deterministic;
- verifies the default `60` is forwarded;
- verifies a custom `12.5` is forwarded;
- verifies blank, zero, negative, NaN, infinity, delimiter-injected, and whitespace-padded values all fail before fake `gcloud` receives any command;
- continues asserting no remediation-write enablement is forwarded.

Added `runtime/tests/test_grafana_runtime_observability.py` using only the standard library:
- parses the dashboard JSON and verifies all four watchdog metrics/headroom query;
- checks every panel uses the fixed `stageguard-prometheus` datasource;
- verifies source-controlled dashboard provider settings and read-only Compose mounts;
- verifies alert UID/query/dashboard-panel binding, evaluation duration, and severity;
- verifies NoData is not conflated with a deadline event;
- rejects embedded contact points, policies, auth headers, webhooks, passwords, or token fields in the alerting file.

Commits this run:
- `8127c5023d429bcbb26a25bb7192382d9d60306f` — provision StageGuard runtime dashboard provider
- `1b1521ff5bcf66244928049ebe4a07e5099fd6e5` — add StageGuard runtime watchdog dashboard
- `8848f4e7881b48bc446f042998210796720fe4cf` — add initial remediation watchdog alert
- `fa83fe10194b2963b4b92ead63af7f2512dde3a9` — mount provisioned StageGuard dashboards
- `7c58ec5b6c42788ef07a99844017aba16c4c9a4f` — expose validated remediation watchdog deploy setting
- `f0121fbe0b69dd8a8482bdd38dbf63428227927b` — keep watchdog alert high signal on missing data
- `e7fa223a17ab88e2efcfd1f376f22490bf131c9e` — reject explicit blank remediation watchdog setting
- `fe945b3b33c7747f6448abb9ad55c0c20b0f1c8e` — cover remediation watchdog deploy contract
- `be6439893664105980dd405cc4b85584e1cb8cec` — test remediation watchdog deploy validation
- `d36f4e2eaf0518b44f549ac542a1ed3e3066150e` — test Grafana watchdog dashboard and alert provisioning

### Tests / checks / results

Validation performed in this run:
- Re-fetched the committed dashboard JSON and visually verified the stable UID, panel definitions, four metric expressions, fixed datasource UID, and headroom query.
- Re-fetched the alert rule after correction and verified `noDataState: NoData`, `execErrState: Error`, dashboard/panel binding, and the exact deadline metric query.
- Re-fetched the deploy helper after correction and verified explicit-blank detection occurs before the numeric checks and before `gcloud run deploy`.
- Added credential-free regression coverage for both Grafana provisioning and the fake-gcloud deployment path.
- Attempted a fresh `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git` followed by the focused unittest suite. The execution container still failed at DNS resolution with `Could not resolve host: github.com`, so the checkout never occurred and no executable green-suite claim is made.
- Did not create, trigger, or rerun any GitHub Actions workflow.

No external Grafana instance, Grafana Cloud stack, notification destination, MCP server, Google Cloud project, Cloud Run service, Secret Manager secret, IAM policy, Gemini endpoint, checkpoint object, or remediation endpoint was modified.

### Decisions made

1. The watchdog alert means one thing only: StageGuard has observed `deadline_exceeded=1`. Missing telemetry remains `NoData`, not a synthetic critical deadline breach.
2. Notification routing is intentionally absent from the repository because a personal/open-source deployment cannot safely assume Slack, PagerDuty, email, webhook, or other destinations. Users can attach their own notification policy/contact point.
3. Dashboard files and rule files are source-controlled and not UI-editable by default, preventing drift between local/demo environments and committed observability intent.
4. The dashboard uses the existing stable Prometheus datasource UID instead of introducing another datasource or Grafana credential path.
5. Watchdog tuning is safe to expose in the standard deploy helper because it changes only readiness timing; it does not grant or activate remediation write capability.
6. An explicitly blank watchdog value is configuration error, not a request for the default. This keeps shell deployment behavior aligned with the Cloud Run entrypoint.
7. No CI was used merely to compensate for the automation container's transient DNS limitation.

### Current blockers / unknowns

- `runtime.tests.test_grafana_runtime_observability`, `runtime.tests.test_cloud_run_deploy_contract`, `runtime.tests.test_cloud_run_deploy_shell`, `runtime.tests.test_cloudrun_entrypoint`, and the focused runtime/API watchdog suite still need execution from a runnable checkout.
- The local Compose Prometheus currently scrapes the deterministic simulator, not a StageGuard API process. Therefore the new runtime-safety dashboard/rule becomes meaningful when a Prometheus-compatible backend is configured to scrape the StageGuard API `/metrics`; the local default stack will otherwise correctly show NoData for these runtime gauges.
- The file-provisioned alert has no notification route/contact point by design; operators must attach one appropriate to their environment.
- The production deployment documentation has not yet been expanded with a concrete Prometheus/Grafana Cloud scrape mapping for the StageGuard API runtime metrics.
- A hung Python remediation provider call still cannot be forcibly interrupted safely; readiness is withdrawn and observability now surfaces it, but process replacement remains the supervisor/platform responsibility.
- The exact Cloud Storage object Policy Troubleshooter tuple still needs one authorized disposable-project acceptance run.
- Gemini deployment doctor and real Vertex AI acceptance smoke still need authorized disposable-project credentials.

## Single best next step

**Close the runtime-metrics ingestion gap: add a documented, modular Prometheus/Grafana Cloud scrape path for StageGuard's authenticated `/metrics` endpoint (without weakening IAP/auth), plus a local credential-free fixture or proxy target that lets the provisioned dashboard and watchdog alert receive realistic StageGuard runtime metrics during Docker rehearsal. Then add an acceptance check that queries Grafana/Prometheus for the four watchdog series and proves the deadline alert transitions without contacting a real remediation provider.**

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
- Grafana now has a source-controlled runtime-safety dashboard and a critical remediation deadline alert bound to the watchdog metrics.
- Gemini acceptance smoke defaults to zero model calls and requires explicit `--execute`.
- Standard Cloud Run deployment keeps production remediation disabled.

## Validation baseline retained

- Local onboarding doctor: 8 tests passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable run: 81/81 passed.
- Historical full suite baseline: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Live Docker rehearsal: PASS twice consecutively.
- Official Grafana MCP read-only smoke path: PASS using `grafana/mcp-grafana:1.3.0`.
- Incident flow: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.
