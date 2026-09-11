# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The current vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded diagnosis, optional Gemini briefing, revision-bound approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated metrics bridging, stale/scrape detection, pinned local acceptance images, strict Prometheus/MCP evidence parsing, structured evidence-unavailable abstention, fail-closed operator handling for observability-plane outages, payload-integrity validation on the private Cloud Run metrics bridge, and an opt-in disposable Prometheus acceptance harness for the complete private Cloud Run scrape chain.

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

## Run log — 2026-09-11 — private Cloud Run metrics acceptance harness

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected:
- `runtime/cloud_run_metrics_bridge.py`
- `runtime/tests/test_cloud_run_metrics_bridge.py`
- `docs/cloud-run-metrics-bridge-safety.md`
- repository runtime/root layout and current acceptance/testing conventions

Rechecked current official Google Cloud documentation for Cloud Run service-to-service authentication and ID-token generation, plus current Prometheus startup/query documentation. The documented model remains a Google-signed ID token for the receiving Cloud Run service audience, with the caller holding the minimum invocation role. Prometheus continues to expose target health through the generated `up` series and its HTTP query API.

Official references reviewed:
- https://cloud.google.com/run/docs/authenticating/service-to-service
- https://cloud.google.com/docs/authentication/get-id-token
- https://prometheus.io/docs/prometheus/latest/querying/api/
- https://prometheus.io/docs/prometheus/latest/configuration/configuration/

### Exact changes made

#### Added opt-in private Cloud Run acceptance harness

Created `runtime/cloud_run_metrics_acceptance.py`.

The harness validates an already-provisioned private StageGuard Cloud Run service through the exact observability path:

```text
anonymous negative check
  -> ADC ID token
  -> private Cloud Run /metrics
  -> StageGuard sentinel validation
  -> local authenticated metrics bridge
  -> bridge /readyz
  -> bridge /metrics
  -> disposable Prometheus
  -> up{job="stageguard-cloud-run-acceptance"} == 1
```

Safety properties:
- accepts only an HTTPS service origin through the existing bridge normalizer;
- first performs a no-token request and requires HTTP 401 or 403, proving the test service is not anonymously exposing `/metrics`;
- reuses `CloudRunMetricsClient`, so ADC token minting, audience handling, authenticated invocation, response-size limits, and StageGuard sentinel validation are the production code path rather than a parallel implementation;
- starts the bridge only after an authenticated upstream fetch succeeds;
- exposes the bridge on `0.0.0.0` only for the bounded lifetime needed by Docker host-gateway access;
- writes a temporary Prometheus config containing only the local bridge target and no credentials;
- starts a disposable `--rm` Prometheus container with a read-only config mount and a loopback-only published query port;
- requires exactly one Prometheus `up` sample and requires it to be finite and exactly `1`;
- tears down Prometheus and the bridge in `finally` cleanup;
- never creates IAM grants, changes Cloud Run, invokes StageGuard lifecycle/remediation endpoints, or triggers CI;
- never prints ID tokens, provider response bodies, ADC exception messages, or unexpected provider exception text.

Default disposable image remains aligned to the repository acceptance pin: `prom/prometheus:v3.13.3`.

Commit:
- `1d9a6b2810cd505d51ecc5ffd764178511f253d1` — add private Cloud Run metrics acceptance harness

#### Added credential-free harness regressions

Created `runtime/tests/test_cloud_run_metrics_acceptance.py`.

Coverage includes:
- anonymous upstream acceptance only for HTTP 401/403;
- Prometheus config contains only the local bridge target and no auth material;
- exact single-series `up == 1` success contract;
- ambiguous target rejection;
- `0`, nonnumeric, `NaN`, `Inf`, and `-Inf` rejection;
- Docker preflight error sanitization;
- disposable `--rm` container behavior;
- loopback-only Prometheus port publishing;
- read-only config mount;
- absence of privileged/container-network escalation flags;
- CLI sanitization of unexpected provider exception text.

Commit:
- `43841d15945d2e0b04a6ea7cf6951ef0fefbecf1` — add credential-free metrics acceptance regressions

#### Documented the real disposable-project procedure

Expanded `docs/cloud-run-metrics-bridge-safety.md` with:
- exact prerequisites;
- one-command usage through `STAGEGUARD_METRICS_TARGET`;
- optional explicit audience/image overrides;
- ordered pass criteria;
- explanation of why the safe negative test is an anonymous request rather than temporary IAM revocation;
- explicit list of operations the harness never performs;
- Docker bridge exposure/cleanup rationale;
- sanitized failure interpretation.

The previous future-tense acceptance checklist is now backed by an implementation rather than remaining documentation-only.

Commit:
- `1b14fb5badf6530113d33545cc9e7df01d98791e` — document disposable Cloud Run metrics acceptance

### Checks / results

Attempted a fresh executable checkout and focused test run:

```bash
git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard
cd /tmp/stageguard
python -m unittest runtime.tests.test_cloud_run_metrics_bridge runtime.tests.test_cloud_run_metrics_acceptance
```

The execution container again failed before checkout with:

```text
Could not resolve host: github.com
```

Therefore no claim is made that the new acceptance regression module, existing bridge tests, Playwright acceptance, full unittest suite, or Docker rehearsal is green in this run.

Repository writes and post-write persistence succeeded through the connected GitHub integration. No GitHub Actions workflow was created, triggered, rerun, or modified. No GCP/IAM/Cloud Run, Grafana Cloud, Gemini, audit, checkpoint, incident, approval, remediation, or recovery resource was changed.

### Decisions

1. Reuse the production `CloudRunMetricsClient` instead of implementing a second token/request path in the harness.
2. Prove privacy with an anonymous/no-token negative request rather than temporarily revoking IAM; acceptance must be non-destructive.
3. Keep tokens entirely inside the bridge client and never place bearer credentials in generated Prometheus configuration.
4. Use disposable Prometheus because target `up == 1` is the final behavior being validated; an HTTP-only bridge check is insufficient.
5. Require one unambiguous `up` result so accidental duplicate acceptance targets fail rather than being silently accepted.
6. Bind Prometheus's host port to loopback and mount generated config read-only; do not use privileged Docker or host networking.
7. Keep the harness completely opt-in and outside CI to avoid GCP charges, credential coupling, noisy workflows, and unsafe implicit cloud operations.
8. Preserve failure sanitization at the CLI boundary; unexpected exceptions expose only their class, not provider text.

### Blockers / unknowns

- The new `runtime/tests/test_cloud_run_metrics_acceptance.py` still needs execution in a runnable checkout.
- The real acceptance harness requires an existing private StageGuard Cloud Run test service, working ADC for a least-privilege invoker identity, and Docker.
- The Playwright evidence-unavailable browser acceptance still needs execution with Chromium.
- The complete pinned Prometheus 3.13.3 + Grafana 13.2.1 watchdog rehearsal still needs a current run after the latest hardening.
- Historical full-suite failures/errors have not yet been re-triaged; no full-suite green claim exists.

## Single best next step

**Run `python runtime/cloud_run_metrics_acceptance.py` against a disposable private StageGuard Cloud Run deployment using a dedicated `roles/run.invoker` identity. If that passes, capture the exact acceptance output and then extend the harness with a bounded recovery check that temporarily stops only the local bridge (not IAM or Cloud Run), proves disposable Prometheus transitions `up: 1 -> 0 -> 1`, and confirms the Cloud Run service itself remains untouched throughout.**

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from last executable run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, but it predates the latest acceptance hardening.
- Official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0` before the latest evidence-availability changes.
- Incident flow baseline: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.
