# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence plane. The current vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, restart reconciliation, operator UI, production deployment hardening, runtime watchdog observability, authenticated Cloud Run metrics ingestion, explicit stale-telemetry detection, a credential-free metrics-outage rehearsal path, and reproducibly pinned Grafana/Prometheus acceptance images.

Core invariants remain unchanged:
- Grafana/MCP is read-only evidence access; infrastructure write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Approval is exact-revision-bound and single-use.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove it.
- Durable checkpoint/audit integrity failures fail closed.
- A healthy watchdog value is trustworthy only while the observability path is delivering fresh samples.
- Loss of observability must never be reclassified as a positive remediation deadline breach.

## Run log — 2026-09-11 — reproducible observability image pins

### Inspected at start

Read `progress.md` completely before making changes. Inspected the repository metadata and the current `docker-compose.yml`, `runtime/tests/test_watchdog_observability_acceptance.py`, and `docs/runtime-metrics-ingestion.md`.

Confirmed the previous handoff's reproducibility gap: the local observability rehearsal still used `prom/prometheus:latest` and `grafana/grafana:latest`, allowing upstream behavior to change between StageGuard runs without any repository diff.

Checked current official release sources before choosing pins:
- Grafana's official GitHub releases list `13.2.1` as the latest stable release, published 2026-09-02, including security fixes.
- Prometheus's official GitHub releases list `3.13.3`, published 2026-09-07.
- Prometheus's official release-cycle documentation identifies the 3.13 line as LTS with support through 2027-07-31.

### Exact changes made

#### Pinned local observability images

Updated `docker-compose.yml`:
- `prom/prometheus:latest` -> `prom/prometheus:v3.13.3`
- `grafana/grafana:latest` -> `grafana/grafana:13.2.1`
- retained the already-pinned official Grafana MCP image `grafana/mcp-grafana:1.3.0`

Added adjacent comments explaining why the Prometheus and Grafana versions must not float: the acceptance rehearsal depends on concrete PromQL sample aging, Grafana file-provisioned alert behavior, and the active-alert API contract.

#### Added repository contract test

Added `runtime/tests/test_observability_image_pins.py`.

The test:
- deterministically reads service image values from the Compose file without adding a YAML dependency;
- requires Prometheus to remain on `prom/prometheus:v3.13.3` until an intentional upgrade;
- requires Grafana to remain on `grafana/grafana:13.2.1` until an intentional upgrade;
- rejects `latest` for Prometheus, Grafana, and the Grafana MCP service;
- requires the pin rationale to remain visible next to the relevant Compose configuration.

The initial implementation used a multiline regular expression; it was immediately replaced with a simpler line/block parser to reduce brittleness and keep the guard dependency-free.

#### Documented upgrade/rehearsal policy

Updated `docs/runtime-metrics-ingestion.md` with a new reproducibility section documenting:
- the three concrete observability image pins;
- the release/LTS rationale;
- official release reference URLs;
- the policy that an image upgrade is an explicit repository change that must be accompanied by upstream release-note review and rerunning the complete watchdog deadline + stale-telemetry acceptance rehearsal.

### Commits this run

- `d908babf47caf2ed88c2b36c45b7f793db89b66f` — pin Grafana and Prometheus observability images
- `68ad224be2ab8160859ce314731374bb2950274d` — add observability image pin regression guard
- `71ae90e078aeb4249fd86f0582852f267d303b73` — make image pin guard deterministic
- `174784e0e8147de6dd6400d7934c4cf6aadd167f` — document reproducible observability image pins

### Tests / checks / results

- Re-fetched the committed `docker-compose.yml` and confirmed the exact pins are present on the default branch.
- Performed a local parser sanity check against the contract-test parsing logic; Prometheus, Grafana, and MCP image extraction all returned the expected fixed image values.
- The full committed unittest cannot be executed from a repository checkout in the current execution environment because direct `github.com` checkout/DNS remains unavailable. No green claim is made for the exact committed test module.
- The Docker acceptance rehearsal also remains unexecuted in this environment because a runnable checkout/container stack is unavailable here.
- No GitHub Actions workflow was created, modified, triggered, or rerun.
- No external Grafana, Grafana Cloud, GCP, IAM, Cloud Run, Secret Manager, Gemini, checkpoint, or remediation resource was changed.

### Decisions

1. Use explicit stable version tags now rather than keep `latest`; deterministic version pins eliminate the immediate upstream-drift failure mode without introducing an unverifiable digest value.
2. Prefer Prometheus 3.13.3 because 3.13 is the current documented LTS line, which better matches StageGuard's production-readiness objective than chasing an RC or short-lived minor.
3. Pin Grafana 13.2.1 because it is the current stable patch from the official release feed and includes current security fixes.
4. Keep the pin contract dependency-free so checking Compose image invariants does not itself require installing PyYAML or bringing up Docker.
5. Treat future upgrades as explicit acceptance events: update the pin, review upstream changes, then rerun both the deadline and stale-evidence lifecycles before accepting the new version.

### Blockers / unknowns

- The focused unit tests still need execution from a runnable checkout.
- The full Docker watchdog rehearsal now needs to run against the newly pinned Prometheus 3.13.3 and Grafana 13.2.1 images to confirm actual sample aging, alert pending timing, active-alert API behavior, firing, and resolution.
- Container digests have not been committed because an authoritative registry digest was not available through the current execution path; explicit immutable version intent is materially better than `latest`, but digest pinning can be considered after direct registry verification.
- The authenticated metrics bridge still needs one disposable-project acceptance against a private Cloud Run StageGuard service with a least-privilege invoker identity.
- Cloud Storage Policy Troubleshooter and live Gemini/Vertex acceptance still require authorized disposable-project credentials.

## Single best next step

**Run the complete credential-free Docker observability rehearsal against the newly pinned Prometheus 3.13.3 + Grafana 13.2.1 stack on the first environment with a runnable checkout. If it passes, capture that exact acceptance baseline; if the Grafana active-alert API or PromQL behavior differs, fix the acceptance/parser/provisioning contract against these pinned versions rather than changing the pins blindly.**

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from last executable run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively; it predates the new watchdog freshness acceptance path and the new explicit image pins.
- Official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`.
- Incident flow baseline: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.
