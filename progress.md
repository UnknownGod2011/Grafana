# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence and observability plane. The core vertical slice is implemented: deterministic broadcast telemetry, Prometheus/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, explicit human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, and a same-origin operator cockpit.

The repository has moved beyond hackathon/demo-only work into **personal open-source productization mode**. Preserve the proven demo path, but prioritize concrete improvements that make real Grafana Cloud/self-hosted onboarding, production operation, deployment, testing, and maintainability better.

Core safety invariants:

- Grafana is the evidence plane; infrastructure write credentials remain isolated from Grafana/MCP access.
- Gemini is optional/advisory and cannot mutate approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact evidence revision.
- Remediation success is never inferred from the action response; fresh Grafana telemetry must prove recovery.
- Local demo credentials/state remain under gitignored `.stageguard/` and `runtime/.secrets/` paths.
- Authenticated local/GCS checkpointing, audit-chain/anchor verification, execution reconciliation, and no-replay protections remain implemented and covered by focused regressions.

## Run log — 2026-09-09 — production onboarding doctor

### Inspected at start

Read `progress.md` completely before choosing work. Inspected current `main`, the judge-facing release pass, `README.md`, `runtime/onboarding.py`, and `runtime/preflight.py`. Confirmed that StageGuard already had a strict live preflight for metrics + Loki, but first-time real users still had to infer basic local prerequisites such as Python version, telemetry-config validity, Grafana URL, token-file location, and the official Grafana MCP launcher before that preflight could succeed.

### Exact changes made

1. Added `scripts/stageguard_doctor.py` as a dependency-free, credential-safe onboarding prerequisite checker.
   - Validates Python 3.11+.
   - Loads the existing strict versioned telemetry mapping through `load_telemetry_profile()` rather than duplicating config parsing.
   - Validates `GRAFANA_URL` structure without making a network request.
   - Validates that `GRAFANA_SERVICE_ACCOUNT_TOKEN_FILE` exists and is non-empty **without reading or printing its contents**.
   - Warns on POSIX token-file permissions broader than `0600`.
   - Checks whether the configured `STAGEGUARD_MCP_COMMAND` launcher is locally available; supports both direct MCP binaries and Docker/Podman launchers.
   - Reports optional activation-file presence without making it a prerequisite for the preflight itself.
   - Emits concise actionable next steps and supports `--json` for setup automation.
   - Performs no PromQL/LogQL, no remote Grafana calls, no secret reads, and no mutations.
2. Updated `README.md` production onboarding to make the doctor the first command before the existing live `runtime/preflight.py` activation step.
3. Updated repository-structure documentation to include the new onboarding doctor.

### Tests / checks / results

- The doctor intentionally reuses the production telemetry loader, so config validation remains single-sourced.
- The implementation uses only Python standard-library modules plus existing repository code.
- This automation environment does not expose a checked-out runtime for executing repository Python commands, so the new CLI was not executed here; no runtime PASS claim is made.
- No live Grafana, Google Cloud, Gemini, remediation endpoint, token, Devpost, or other external resource was touched.
- No GitHub Actions workflow was added or manually triggered.

### Decisions made

1. **Separate prerequisite diagnosis from live evidence preflight.** Users should be told exactly which local prerequisite is missing before StageGuard attempts MCP queries.
2. **Never inspect token contents in the doctor.** File existence/size/permissions are enough for local setup diagnostics; the live MCP preflight remains responsible for proving the credential actually works.
3. **Reuse existing contracts.** The doctor imports StageGuard's strict telemetry loader instead of creating a second schema or accepting arbitrary datasource/query configuration.
4. **Keep live validation authoritative.** A green doctor means only “ready to run preflight,” not “production ready.” `runtime/preflight.py` still has to prove the actual Grafana MCP metric/Loki evidence paths and write expiring activation records.

### Current blockers / unknowns

- The new doctor still needs execution on Linux/macOS and Windows checkouts to empirically confirm path/permission presentation.
- Live official Grafana MCP acceptance still requires a reachable Grafana instance and least-privilege service-account token.
- Real Google Cloud deployment acceptance remains credential/resource work.
- The previously reported broader full-suite failures/errors remain to be triaged as productization work; they were not reclassified or hidden in this run.

## Single best next step

**Add credential-free tests for `scripts/stageguard_doctor.py` covering valid config, missing/invalid Grafana URL, missing/non-empty token files, MCP executable discovery, POSIX permission warning, JSON output, and exit codes; then run that focused suite on both Windows and Linux when a checkout/runner is available.**

## Previous run summary

The previous work completed the judge-facing cockpit/provenance pass, Windows checkpoint/retention portability fixes, and release rehearsal telemetry gating. Those proven paths remain intact while the project now shifts toward real-user onboarding and production operation.

## Historical run — 2026-09-09 — release rehearsal telemetry gating

### Inspected at start

Read `progress.md` completely before choosing work. Inspected current `main`, `scripts/demo_local.py`, `runtime/bootstrap.py`, the deterministic simulator, Prometheus scrape configuration, Grafana MCP smoke path, and investigation/recovery telemetry contracts. A concurrent commit also added open-source/submission presentation assets; those files were preserved rather than overwritten.

The highest-value concrete demo risk was timing-based evidence readiness. `demo_local.py` used fixed 5–6 second sleeps after reset/fault injection. That assumes Prometheus has already scraped enough samples for the exact StageGuard diagnosis queries. On a cold Docker start, slower host, or repeated take, this could allow the operator to click Investigate before `rate(video_frames_dropped_total[2m])` is queryable and cause an avoidable abstain.

### Exact changes made

1. Added `scripts/demo_release.py` as a release-critical rehearsal wrapper around the existing demo runner.
   - Recreates the local compose stack before a take so stale Prometheus history from previous rehearsals cannot contaminate the recording.
   - Reuses `demo_local.up(...)`, preserving the existing simulator/Grafana/token/MCP/API startup path rather than forking product orchestration.
   - Queries the local Prometheus HTTP API with the Python standard library only.
   - Waits for the actual healthy evidence predicates before the take: `uplink-b` packet loss below 1% and Camera 3 dropped-frame rate below 1/s.
   - Injects the existing deterministic fault only after the operator is ready.
   - Waits until the actual incident predicates are queryable before telling the operator to investigate: `uplink-b` packet loss above 5% and Camera 3 dropped-frame rate above 1/s.
   - Emits `INCIDENT EVIDENCE READY — CLICK INVESTIGATE NOW` only after both evidence gates pass.
   - Fails closed on malformed Prometheus responses, multiple series, non-numeric values, empty evidence beyond the bounded timeout, or unavailable local services.
   - Supports the same optional `--gemini` and `--open` switches as the normal local demo.
2. Preserved all concurrent repository work and avoided force-updating `main` after detecting the branch had advanced.
3. No production/cloud/remediation behavior was broadened and no GitHub Actions workflow was added or manually rerun.

### Tests / checks / results

- The new release gate is dependency-free beyond the already-required local Docker/StageGuard stack and uses deterministic local endpoints only.
- Its Prometheus parser accepts only a successful single-series vector result, treats an empty vector as not-ready, and fails closed on every other shape.
- This automation environment still cannot run the repository's Docker compose stack, so the new release rehearsal has not been empirically executed here and no green end-to-end claim is made.
- No live Grafana Cloud, Gemini, Google Cloud, IAP, Secret Manager, Devpost, or production remediation resource was touched in this run.

### Decisions made

1. **Replace arbitrary sleeps with exact evidence gates.** This makes demo reliability depend on the telemetry StageGuard actually consumes rather than host speed.
2. **Use a recreated compose stack for release rehearsals.** The checked-in demo compose configuration has no persistent data volumes, so recreation cheaply removes stale Prometheus samples between takes.
3. **Keep `demo_local.py` authoritative.** The release wrapper composes the existing runner rather than duplicating startup logic.
4. **Stay in demo freeze.** The next work must be driven by a concrete failure from the real rehearsal, not another speculative feature.

### Current blockers / unknowns

- Docker Desktop/Linux engine must be running on the development machine for the real rehearsal.
- The pinned `grafana/mcp-grafana:1.3.0` image still needs empirical execution through the existing official MCP smoke gate on that machine.
- The complete Python runtime suite has not run in this automation environment.
- Real Google Cloud/Grafana Cloud acceptance remains credential/resource work and is not required for the deterministic local operator path.

## Historical final submission status — 2026-09-09

Demo: BLOCKED ON LOCAL DOCKER ENGINE — `docker compose` is installed, but Docker Desktop's Linux engine was unavailable on this laptop; the repository's deterministic demo runner remains the intended judge-machine path.

Grafana MCP: NOT LIVE-VERIFIED HERE — the checked-in runner gates readiness on the official `grafana/mcp-grafana:1.3.0` read-only smoke query.

Gemini: NOT USED — optional and intentionally not faked without working Vertex/ADC credentials.

Video: NOT CREATED — no honest live runtime capture was possible without Docker; do not submit a fabricated demo video.

Devpost: NOT SUBMITTED — Devpost rules were inspected; the current browser session is not authenticated.

Submission: BLOCKED

Any remaining blocker: Start Docker Desktop on a judge-capable machine, run the documented demo twice, record/upload the required public 3-minute video, then authenticate Devpost and submit to the Grafana Labs partner track.

## Post-submission code portability fixes — 2026-09-09

- Fixed Windows checkpoint persistence: `JsonCheckpointStore` and `SignedJsonCheckpointStore` no longer call unavailable `os.fchmod` while holding an open temporary descriptor.
- Fixed Windows retention persistence: temporary audit output now closes cleanly before cleanup, backup durability uses a writable descriptor, and directory fsync is skipped where Windows cannot open directory descriptors.
- Verification: checkpoint schema, incident checkpoint, retention planner, and focused incident/Gemini/MCP/remediation tests were rerun; the core focused suite is green with 35/35 passing.
- Full suite after portability fixes: 352 tests, 9 failures, 15 errors, 19 skipped. Remaining failures are contract/platform-specific outside the demo path; no claim of full-suite green.

## Final judge-facing pass — 2026-09-09

- Added a judge-first README opening with the closed-loop story, architecture diagram, 60-second architecture, and release runner command.
- Added a judge-facing presentation layer to the existing cockpit. It surfaces Camera 3 degradation, uplink-b root cause, confidence, evidence revision, evidence labels, human approval, and the `ACTION ACCEPTED ≠ INCIDENT RESOLVED` verification transition.
- Added bounded `evidence_source` metadata to lifecycle responses: Grafana MCP provider, read-only access, Prometheus datasource UID, investigation query count, recovery sample count, and last tool latency. Raw queries and secrets remain excluded.
- Focused judge/core/API/UI suite: 81/81 passed. Full suite: 352 tests, 9 failures, 15 errors, 19 skipped.
- Created `FINAL_RELEASE_REPORT.md` with the current readiness status and criterion-to-proof matrix. Architecture is frozen after this pass.
