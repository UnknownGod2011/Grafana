# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence and observability plane. The core vertical slice is implemented: deterministic broadcast telemetry, Prometheus/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, explicit human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, and a same-origin operator cockpit.

The repository is in **demo freeze / release-critical integration mode**. Do not add architecture or security features unless they directly unblock the end-to-end operator demonstration.

Core safety invariants:

- Grafana is the evidence plane; infrastructure write credentials remain isolated from Grafana/MCP access.
- Gemini is optional/advisory and cannot mutate approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact evidence revision.
- Remediation success is never inferred from the action response; fresh Grafana telemetry must prove recovery.
- Local demo credentials/state remain under gitignored `.stageguard/` and `runtime/.secrets/` paths.
- Authenticated local/GCS checkpointing, audit-chain/anchor verification, execution reconciliation, and no-replay protections remain implemented and covered by focused regressions.

## Run log — 2026-09-09 — release rehearsal telemetry gating

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

## Single best next step

**Run `python scripts/demo_release.py --open` on a Docker-capable checkout and complete one full take: verified healthy baseline → verified fault evidence → Investigate → optional Gemini briefing → exact revision approval → Execute → telemetry `recovered`. Fix only the first concrete blocker encountered. Once it passes twice consecutively, freeze code and record the demo.**

## Previous run summary

The previous run added the one-command `scripts/demo_local.py` vertical-slice runner, shortened only the post-remediation dropped-frame recovery query window to 15 seconds, and aligned `DEMO.md` to the real Grafana MCP → diagnose → approve → remediate → telemetry-verify workflow. Concurrent follow-up work added presentation/open-source submission assets without changing that runtime contract.
