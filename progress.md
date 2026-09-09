# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the runtime evidence and observability plane. The core vertical slice is implemented: deterministic broadcast telemetry, Prometheus/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, explicit human approval, local safe remediation, Grafana-based recovery verification, authenticated lifecycle state, and the same-origin operator cockpit. Local `signed-json` checkpoints and the retention coordinator now also have restart/no-replay acceptance coverage.

The project is now in **demo freeze / release-critical integration mode**: stop adding architecture/security features unless they directly unblock the end-to-end operator demonstration.

Core safety invariants:

- Grafana is the evidence plane; infrastructure write credentials stay isolated from Grafana/MCP access.
- Gemini is optional/advisory and cannot mutate approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact evidence revision.
- Remediation success is never inferred from the action response; consecutive Grafana telemetry samples must prove recovery.
- Local demo credentials/state remain under gitignored `.stageguard/` and `runtime/.secrets/` paths.
- `/readyz` remains the hardened production readiness boundary; the local demo runner separately proves the actual MCP query path before opening the cockpit.

## Run log — 2026-09-09 — one-command demo vertical slice hardening

### Inspected at start

Read `progress.md` completely before choosing work. Inspected current `main`, `docker-compose.yml`, `runtime/bootstrap.py`, `runtime/bootstrap_grafana.py`, `runtime/mcp_smoke.py`, `runtime/mcp_metric_client.py`, `runtime/simulator.py`, `runtime/prometheus.yml`, `runtime/telemetry.py`, `runtime/remediation.py`, `runtime/api.py`, and `DEMO.md`.

Confirmed the checked-in highest-priority goal had shifted from more retention work to making the real operator path reproducible. Also identified a concrete demo blocker in recovery semantics: investigation intentionally uses a long 2-minute dropped-frame rate window, but reusing that same window for the bounded recovery loop can keep historical fault samples elevated beyond the 25-second verification budget even after remediation succeeds.

### Exact changes made

1. Added `scripts/demo_local.py` as the one-command local demonstration orchestrator.
   - `python scripts/demo_local.py demo --open` starts the simulator, Prometheus, and Grafana; resets the broadcast healthy; bootstraps/reuses a short-lived Viewer Grafana service-account token; executes the real official Grafana MCP read-only Prometheus smoke query; starts the StageGuard API/cockpit using the HMAC-authenticated local `signed-json` checkpoint backend; writes `.stageguard/demo/readiness.json`; and waits for the operator to press Enter before injecting the deterministic `uplink-b` failure.
   - Also exposes `up`, `fault`, `reset`, `status`, and `stop` commands so recording attempts can be repeated without ad-hoc shell commands.
   - Supports optional `--gemini` only when Vertex AI/ADC is already configured; the deterministic Grafana workflow does not depend on Gemini being available.
   - Generates the local checkpoint HMAC key into gitignored demo state with owner-only permissions and never prints it.
   - Refuses destructive `--fresh` while the StageGuard API is currently alive and avoids signalling a stale PID unless the expected local API endpoint is active.
   - Emits a bounded readiness report containing service health, URLs, and the actual Grafana MCP smoke PASS result, never token values.
2. Hardened the post-remediation telemetry contract for live operations.
   - Kept the 2-minute dropped-frame rate window for investigation context.
   - Changed only the post-action dropped-frame recovery query to a 15-second rate window.
   - This preserves telemetry-based proof while allowing the existing six-attempt / five-second recovery loop to converge after a successful live-broadcast remediation rather than being dominated by old fault samples.
3. Extended `runtime/tests/test_telemetry.py`.
   - Added an explicit regression that recovery uses `[15s]` and no longer inherits `[2m]`.
   - Existing two-query recovery budget and six-query investigation budget remain unchanged.
4. Rewrote `DEMO.md` around the executable repository state.
   - Documents the one-command local start, exact demo URLs, repeat/reset/stop commands, optional Gemini behavior, recording checklist, and a concrete 3-minute sequence.
   - Corrects the product story: Gemini is a revision-bound operator briefing layer; deterministic policy + Grafana evidence remain the safety authority.
   - Explicitly tells the operator to show the official Grafana MCP proof, human approval, and telemetry-verified recovery rather than retention/security internals.

### Tests / checks / results

- `scripts/demo_local.py` passed isolated Python syntax compilation before Git object preparation.
- The new telemetry regression is structurally bounded to the changed recovery query contract.
- A complete Docker/runtime checkout is still unavailable inside this tool environment, so the one-command stack and full Python suite have not been executed here; no green end-to-end claim is made.
- No live Grafana, Gemini, Google Cloud, IAP, Secret Manager, or production remediation resources were touched.
- No GitHub Actions workflow was added, changed, manually triggered, or rerun.

### Decisions made

1. **Freeze feature expansion.** Further work should fix only failures in the recording/deployment vertical slice until the demo is reproducibly green.
2. **Make the real MCP proof a startup gate.** The local demo refuses to declare itself ready unless `runtime/mcp_smoke.py` successfully executes the official read-only Grafana MCP query through Grafana.
3. **Start the recording healthy.** Although the simulator container defaults faulted for deterministic development, the demo runner explicitly resets it and waits for healthy Prometheus samples before fault injection.
4. **Use a short recovery evidence window, not a fake success signal.** The remediation API response still cannot close the incident; the only change is to make the post-action telemetry window compatible with the bounded live verification loop.
5. **Keep Gemini optional for reliability.** If Vertex credentials have not already been rehearsed, record the real Grafana MCP + deterministic safety loop rather than faking or debugging cloud AI during the final recording window.

### Current blockers / unknowns

- The new demo runner has not yet been executed on a Docker-capable checkout.
- Official Grafana MCP response/version behavior still needs one empirical local run against the pinned `grafana/mcp-grafana:1.3.0` image.
- The complete Python runtime suite has not run in this tool environment.
- Real Cloud Run/IAP/GCS/Cloud Logging deployment remains an operator-owned credential/resource step and is not required for the local recording path.

## Single best next step

**Run `python scripts/demo_local.py demo --open` in a real Docker checkout immediately. Do one complete rehearsal from healthy broadcast -> fault -> Investigate -> optional Gemini briefing -> exact revision approval -> Execute -> telemetry `recovered`. Fix only concrete blockers in that path. Once it passes twice consecutively, freeze the repository, record the 3-minute demo using `DEMO.md`, and do not spend remaining time on new features.**

## Previous run summary

The previous run completed the signed local runtime checkpoint -> retention coordinator -> compacted audit -> hardened restart/no-remediation-replay acceptance path, removing the last major local retention composition gap.

## FINAL SUBMISSION STATUS — 2026-09-09

Demo: BLOCKED ON LOCAL DOCKER ENGINE — `docker compose` is installed, but Docker Desktop's Linux engine was unavailable on this laptop; the repository's deterministic demo runner remains the intended judge-machine path.

Grafana MCP: NOT LIVE-VERIFIED HERE — the checked-in runner gates readiness on the official `grafana/mcp-grafana:1.3.0` read-only smoke query.

Gemini: NOT USED — optional and intentionally not faked without working Vertex/ADC credentials.

Video: NOT CREATED — no honest live runtime capture was possible without Docker; do not submit a fabricated demo video.

Devpost: NOT SUBMITTED — Devpost rules were inspected; the current browser session is not authenticated.

Submission: BLOCKED

Any remaining blocker: Start Docker Desktop on a judge-capable machine, run the documented demo twice, record/upload the required public 3-minute video, then authenticate Devpost and submit to the Grafana Labs partner track.
