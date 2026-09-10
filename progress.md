# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence plane. The current vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, restart reconciliation, operator UI, production deployment hardening, runtime watchdog observability, authenticated Cloud Run metrics ingestion, explicit stale-telemetry detection, a credential-free metrics-outage rehearsal path, reproducibly pinned Grafana/Prometheus acceptance images, and live runtime-version attestation in the observability acceptance rehearsal.

Core invariants remain unchanged:
- Grafana/MCP is read-only evidence access; infrastructure write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Approval is exact-revision-bound and single-use.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove it.
- Durable checkpoint/audit integrity failures fail closed.
- A healthy watchdog value is trustworthy only while the observability path is delivering fresh samples.
- Loss of observability must never be reclassified as a positive remediation deadline breach.

## Run log — 2026-09-11 — live observability version attestation

### Inspected at start

Read `progress.md` completely before making changes. Inspected repository metadata plus:
- `docker-compose.yml`
- `runtime/watchdog_observability_acceptance.py`
- `runtime/tests/test_watchdog_observability_acceptance.py`
- `docs/runtime-metrics-ingestion.md`

Confirmed that the repository now pins Prometheus 3.13.3 and Grafana 13.2.1, but the acceptance script previously trusted whatever containers happened to be listening on ports 9090/3000. A stale pre-existing container, manually started image, or locally drifted stack could therefore satisfy the alert lifecycle and produce a misleading PASS against the wrong upstream runtime.

### Exact changes made

#### Added live Prometheus/Grafana version attestation

Updated `runtime/watchdog_observability_acceptance.py` with explicit acceptance-baseline constants:
- `EXPECTED_PROMETHEUS_VERSION = "3.13.3"`
- `EXPECTED_GRAFANA_VERSION = "13.2.1"`

Before the script changes fixture state or begins the watchdog alert lifecycle, it now:
1. waits for Prometheus `/api/v1/status/buildinfo` to become available;
2. waits for Grafana `/api/health` to become available;
3. parses both responses with strict fail-closed helpers;
4. requires the live Prometheus version to exactly equal 3.13.3;
5. requires the live Grafana version to exactly equal 13.2.1;
6. aborts the rehearsal before any scenario manipulation if either runtime differs.

This closes the gap between source-controlled image tags and the actual processes under test. The final PASS message now explicitly states that pinned runtime versions were attested.

The new parsers reject malformed roots, unsuccessful Prometheus build-info responses, missing/non-object data, and missing/blank/non-string version fields instead of treating an unknown runtime as acceptable.

#### Added regression coverage

Updated `runtime/tests/test_watchdog_observability_acceptance.py` to cover:
- the expected Prometheus/Grafana acceptance versions;
- successful Prometheus build-info version parsing;
- fail-closed Prometheus parsing for malformed/error payloads;
- successful Grafana health version parsing;
- fail-closed Grafana parsing for malformed/missing/invalid version payloads.

Existing alert-identity, malformed-alert, stale-query, telemetry-mode, timeout, and loopback-origin regression coverage remains intact.

### Commits this run

- `4014b58fe7bf84a4336c06fe68987ef238adb2b2` — attest live observability versions in acceptance
- `63439700bad9b35154d01477514b4f65ed98b85e` — test observability runtime version attestation

### Tests / checks / results

- Verified through the GitHub API that both commits are on the repository default branch.
- Attempted a fresh `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git` followed by the focused unittest modules.
- The execution environment still failed before checkout with `Could not resolve host: github.com`; therefore the exact committed Python tests did not execute and no green claim is made.
- The Docker observability rehearsal also remains unexecuted in this environment because the repository cannot be checked out here.
- No GitHub Actions workflow was created, modified, triggered, or rerun.
- No external Grafana, Grafana Cloud, GCP, IAM, Cloud Run, Secret Manager, Gemini, checkpoint, or remediation resource was changed.

### Decisions

1. Treat the *running* Grafana/Prometheus versions as part of the acceptance contract, not merely the Compose file contents.
2. Fail before fixture mutation when version identity cannot be proved, so a stale or manually started runtime cannot create a false acceptance baseline.
3. Use official self-reporting endpoints (`/api/v1/status/buildinfo` and `/api/health`) instead of container-name/image heuristics; this verifies the software actually answering the acceptance requests.
4. Keep exact equality for this reproducibility rehearsal. Intentional upgrades require changing both the source-controlled image pin and the attested acceptance version, reviewing upstream release notes, and rerunning the complete lifecycle.
5. Keep this entirely local/credential-free; no production Grafana or Google Cloud resource is needed to prove the observability contract.

### Blockers / unknowns

- The focused unit tests still need execution from a runnable checkout.
- The full Docker watchdog rehearsal still needs to run against the pinned Prometheus 3.13.3 and Grafana 13.2.1 images. It now additionally proves the live runtimes match those versions before alert testing begins.
- Container digests are still not committed because an authoritative registry digest has not been verified through the available execution path.
- The authenticated metrics bridge still needs one disposable-project acceptance against a private Cloud Run StageGuard service with a least-privilege invoker identity.
- Cloud Storage Policy Troubleshooter and live Gemini/Vertex acceptance still require authorized disposable-project credentials.

## Single best next step

**Run the complete credential-free Docker observability rehearsal on the first environment with a runnable checkout. The rehearsal must now first attest live Prometheus 3.13.3 and Grafana 13.2.1, then prove deadline firing/resolution and stale-telemetry firing/resolution. If it passes, capture that exact baseline; if either runtime API or alert behavior differs, fix the acceptance/provisioning contract against these pinned versions rather than weakening the checks.**

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from last executable run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively; it predates the new watchdog freshness acceptance path, explicit image pins, and live runtime-version attestation.
- Official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`.
- Incident flow baseline: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.
