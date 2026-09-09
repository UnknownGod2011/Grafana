# StageGuard — Local Demo + 3-Minute Recording Runbook

StageGuard is an incident commander for live media operations. Grafana is the runtime evidence plane; the deterministic safety core diagnoses bounded failure hypotheses, requires explicit human approval for remediation, and returns to Grafana telemetry before it declares recovery. Gemini is an optional, revision-bound operator briefing layer and has no remediation authority.

## Fastest reliable local start

Prerequisites: Python 3.11+ and Docker with the Compose plugin.

From the repository root:

```bash
python scripts/demo_local.py demo --open
```

That one command:

1. starts the deterministic broadcast simulator, Prometheus, and Grafana;
2. resets the broadcast to a healthy baseline;
3. creates/reuses a short-lived **Viewer** Grafana service-account token locally;
4. executes the official `grafana/mcp-grafana` read-only Prometheus smoke query;
5. starts the StageGuard API + same-origin operator cockpit with an HMAC-authenticated local checkpoint;
6. writes `.stageguard/demo/readiness.json`;
7. waits for you to press Enter before injecting the visible `uplink-b` fault.

Useful commands:

```bash
python scripts/demo_local.py up --fresh --open
python scripts/demo_local.py fault
python scripts/demo_local.py reset
python scripts/demo_local.py status
python scripts/demo_local.py stop
```

Enable the optional Vertex AI Gemini briefing only when its environment/ADC configuration is already valid:

```bash
python scripts/demo_local.py demo --gemini --open
```

Do **not** turn Gemini on five minutes before recording if the credential path has not already been tested. The deterministic Grafana → diagnosis → approval → remediation → Grafana verification loop works without it.

### Demo URLs

- Operator cockpit: `http://127.0.0.1:9110/console`
- Grafana: `http://127.0.0.1:3000` (`admin` / `stageguard-local-only`, local demo only)
- Prometheus: `http://127.0.0.1:9090`
- Simulator state: `http://127.0.0.1:9108/state`
- StageGuard API log: `.stageguard/demo/stageguard-api.log`
- Demo readiness report: `.stageguard/demo/readiness.json`

Generated state and secrets are under gitignored `.stageguard/` / `runtime/.secrets/` paths. The script does not create or use production credentials.

## What must be visible in the recording

The goal is not to show a chatbot. Show this closed loop:

`broadcast fault → Grafana evidence → bounded diagnosis → human approval → safe action → Grafana recovery proof`

The official Grafana MCP query must be real. The action endpoint returning HTTP 200 is **not** sufficient evidence of recovery.

## Recommended 3-minute sequence

### 0:00–0:15 — Stakes + healthy system

Show the StageGuard cockpit and Grafana.

Narration:

> “A live broadcast can lose viewers in seconds. StageGuard gives the production an incident commander that investigates through Grafana, keeps humans in control of consequential actions, and verifies the recovery from telemetry.”

Keep Camera 1/2/3 healthy at the start.

### 0:15–0:30 — Inject the failure

In the terminal running `demo_local.py`, press Enter.

The deterministic simulator creates:

- `uplink-b` packet loss at 18%;
- Camera 3 frame drops;
- normal Camera 3 encoder CPU/GPU;
- healthy peer cameras/uplink.

Show Grafana changing. Do not announce the root cause yet.

### 0:30–1:15 — Investigate through Grafana

In the cockpit click **Investigate**.

StageGuard executes the fixed six-query evidence contract through the official Grafana MCP path and should conclude:

- status: **diagnosed**;
- hypothesis: **uplink-b packet loss**;
- affected feed: **cam-3**;
- encoder CPU/GPU are normal;
- peer uplink/feed evidence is healthy.

Show the structured evidence and revision. Do not expose chain-of-thought; the evidence itself is the proof.

If Gemini is already configured, request the revision-bound briefing here. Frame it as operator communication, not the safety authority.

### 1:15–1:45 — Human-controlled action

Show the proposed `recover_uplink` action and the exact evidence revision.

Type/confirm the revision and explicitly approve it. Then execute.

Narration:

> “The model cannot directly execute infrastructure changes. Approval is single-use and bound to the evidence revision.”

### 1:45–2:20 — Prove recovery

The simulator action stops the uplink fault, but StageGuard keeps the incident open until telemetry is healthy.

Recovery uses:

- current `uplink-b` packet loss; and
- a short 15-second dropped-frame-rate window suitable for bounded live-production verification.

Require consecutive healthy samples before showing **recovered**.

Keep Grafana visible during this section.

### 2:20–2:45 — Product credibility

Briefly show:

- the incident audit/timeline;
- approval provenance;
- recovery samples;
- `/metrics` or the bounded runtime health indicators if useful.

One sentence is enough for the deeper safety work:

> “StageGuard also persists authenticated incident state and fails closed on multi-instance checkpoint or ambiguous execution races, but the operator flow stays simple.”

Do not spend the demo explaining retention internals.

### 2:45–3:00 — Close

Show this architecture strip:

`Live Production → Grafana → Grafana MCP → StageGuard → Human-approved Action → Grafana Verification`

Final line:

> **“StageGuard doesn't generate the show. It keeps the show on air.”**

## Recording checklist

Before recording, all of these should be true:

- `python scripts/demo_local.py status` shows simulator, Prometheus, Grafana, and StageGuard API healthy;
- `.stageguard/demo/readiness.json` has `grafana_mcp_read_only_query: true`;
- the simulator is healthy before the take;
- one test fault produces a `diagnosed` result;
- approval + execute reaches `recovered` within the bounded verification loop;
- the cockpit can be reset/restarted for a second take;
- no terminal window shows credentials or token files.

If the first full rehearsal does not pass, fix **only the blocker in this path**. Do not add more architecture/security features before recording.

## Backup plan

If optional Gemini/Vertex credentials are unavailable, record the deterministic Grafana MCP workflow without Gemini. Do not fake a model call.

If a remote deployment is unavailable, record the local Docker stack. The strongest proof is the real official Grafana MCP query and the complete observe → diagnose → approve → act → verify loop, not the hosting location.

If a recording attempt gets into a bad state:

```bash
python scripts/demo_local.py stop
python scripts/demo_local.py demo --open
```

The `demo` command starts from fresh StageGuard demo state and resets the simulated broadcast to healthy before fault injection.
