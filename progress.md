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
- The runtime-safety sentinel is label-free by contract; any additional labeled series in that metric family makes the payload ambiguous and must fail closed.
- Cloud Run metrics acceptance must never grant IAM, print credentials, mutate incidents, or require making StageGuard public.
- Recovery acceptance may interrupt only the local metrics bridge; it must not mutate Cloud Run, IAM, or StageGuard lifecycle state.

## Run log — 2026-09-11 — sentinel-family ambiguity hardening

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected:
- `runtime/cloud_run_metrics_bridge.py`
- `runtime/cloud_run_metrics_acceptance.py`
- `runtime/tests/test_cloud_run_metrics_bridge.py`
- `runtime/tests/test_cloud_run_metrics_acceptance.py`
- `docs/cloud-run-metrics-bridge-safety.md`

The previous handoff identified real private Cloud Run acceptance as the strongest validation step. That still requires a runnable checkout plus external ADC/Cloud Run credentials, so this run inspected the trust boundary for useful credential-free hardening rather than stopping.

### Finding

`validate_stageguard_metrics()` correctly rejected a payload whose only deadline sentinel was labeled, but it ignored labeled sentinel-family samples whenever a valid bare sentinel was also present. Example:

```text
stageguard_remediation_execution_deadline_exceeded 0
stageguard_remediation_execution_deadline_exceeded{source="shadow"} 1
```

Because the validator only collected a first token exactly equal to the bare metric name, this body could pass readiness validation even though the forwarded Prometheus exposition contained two semantically conflicting series in the safety-critical metric family. The bridge contract says the sentinel is authoritative and label-free, so accepting an additional labeled series is unnecessarily ambiguous.

### Exact changes made

#### Hardened the private Cloud Run metrics payload validator

Updated `runtime/cloud_run_metrics_bridge.py`.

Changes:
- added `_is_sentinel_family_token()` to recognize either the exact label-free sentinel token or the same metric name followed by a Prometheus label set;
- retained the exact bare sentinel as the only authorized sample form;
- now rejects any labeled sentinel-family series immediately with a sanitized `RuntimeError`;
- rejects the labeled family series even if a valid bare sentinel is also present before or after it;
- does not confuse similarly prefixed metrics such as `stageguard_remediation_execution_deadline_exceeded_total` with the sentinel family;
- updated module/docstring comments to state that one finite label-free boolean sentinel **and no additional sentinel-family series** is required.

Commit:
- `f9f2d5edb118a43e1701a00a515f907733558fc2` — harden metrics sentinel family validation

#### Added focused credential-free regression coverage

Added `runtime/tests/test_cloud_run_metrics_bridge_sentinel_family.py`.

Coverage proves:
- exactly one bare `0` or `1` sentinel is accepted;
- a valid bare sentinel plus a labeled family series is rejected for either labeled value;
- ordering does not matter: labeled-before-bare is also rejected;
- a labeled-only sentinel fails closed;
- a similarly prefixed but different metric name does not create a false-positive ambiguity.

Commit:
- `89bf1a163dd3137910e427b99d9df9f2efe29450` — test metrics sentinel family ambiguity

### Checks / results

Re-read the updated validator from the repository after the write and confirmed the expected family-detection and fail-closed branches are present.

Attempted a fresh executable checkout and focused test run:

```bash
git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard
cd /tmp/stageguard
python -m unittest \
  runtime.tests.test_cloud_run_metrics_bridge \
  runtime.tests.test_cloud_run_metrics_bridge_sentinel_family \
  runtime.tests.test_cloud_run_metrics_acceptance
```

The execution container failed before checkout with:

```text
Could not resolve host: github.com
```

Therefore no claim is made that the new regression, existing bridge tests, acceptance tests, browser acceptance, full unittest suite, or Docker rehearsal is green in this run.

Repository writes succeeded through the connected GitHub integration. No GitHub Actions workflow was created, triggered, rerun, or modified. No GCP/IAM/Cloud Run, Grafana Cloud, Gemini, audit, checkpoint, incident, approval, remediation, or recovery resource was changed.

### Decisions

1. Treat the deadline sentinel as an exact label-free metric contract, not merely as one valid sample somewhere in a larger same-name family.
2. Fail closed on any labeled sample using the safety sentinel metric name, because forwarding ambiguous safety semantics is worse than surfacing scrape/evidence unavailability.
3. Keep the validator intentionally narrow rather than implementing a general Prometheus parser.
4. Keep similarly prefixed but distinct metric names valid so the family check does not accidentally reject legitimate future metrics.
5. Do not add CI just to compensate for the current execution environment's DNS failure.

### Blockers / unknowns

- The new `runtime/tests/test_cloud_run_metrics_bridge_sentinel_family.py` still needs execution in a runnable checkout.
- The updated focused bridge/acceptance suite still needs execution.
- The real acceptance harness requires an existing private StageGuard Cloud Run test service, working ADC for a least-privilege invoker identity, and Docker.
- The Playwright evidence-unavailable browser acceptance still needs execution with Chromium.
- The complete pinned Prometheus 3.13.3 + Grafana 13.2.1 watchdog rehearsal still needs a current run after the latest hardening.
- Historical full-suite failures/errors have not yet been re-triaged; no full-suite green claim exists.

## Single best next step

**In the first runnable environment, execute the focused bridge/sentinel-family/acceptance tests, then run `python runtime/cloud_run_metrics_acceptance.py` against a disposable private StageGuard Cloud Run service using a dedicated least-privilege `roles/run.invoker` identity. Confirm the real ADC -> private `/metrics` -> validated bridge -> Prometheus path completes `up: 1 -> 0 -> 1` and that the new sentinel-family ambiguity regression is green.**

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from last executable run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, but it predates the latest acceptance and sentinel-family hardening.
- Official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0` before the latest evidence-availability changes.
- Incident flow baseline: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.
