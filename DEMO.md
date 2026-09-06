# StageGuard — 3-Minute Judge Demo

## Demo objective

Prove, visibly and quickly, that StageGuard is not a chatbot and not a Grafana dashboard wrapper. The demo must show a real media-production incident, genuine Grafana MCP tool use, bounded agentic action, human control, and telemetry-based verification.

## Narrative

**One-line pitch:** StageGuard is an autonomous incident commander for live media production: it uses Grafana to understand what broke, Gemini to decide what to do, and Grafana again to prove the fix worked.

## Primary scenario

A three-camera live broadcast is healthy. Camera 3 is routed through uplink B. A deterministic fault injector increases packet loss on uplink B, which causes frame drops on Camera 3 while the encoder itself remains healthy.

The correct diagnosis is **network uplink degradation**, not encoder overload.

The correct bounded action is **reroute Camera 3 to uplink A**, requiring operator approval.

The incident is resolved only after Grafana telemetry shows frame drops and packet loss recovering.

## Timeline

### 0:00–0:15 — Establish stakes

Show the live production console:

- Camera 1 healthy
- Camera 2 healthy
- Camera 3 healthy
- broadcast output healthy

Narration: “When a live production fails, operators have minutes—or seconds—to correlate alerts, metrics, logs and dependencies while viewers are already seeing the outage.”

### 0:15–0:30 — Trigger failure

Inject uplink-B degradation.

Visible effects:

- Camera 3 health turns degraded
- frame-drop metric rises
- Grafana alert appears

Do not explain the cause yet.

### 0:30–1:15 — Agent investigation

StageGuard begins automatically.

The UI should expose concise tool/evidence steps rather than hidden chain-of-thought:

1. alert inspected
2. Camera 3 dropped-frame metric confirmed
3. peer feeds compared
4. encoder resource telemetry checked
5. uplink packet-loss telemetry checked
6. relevant logs/traces checked if available

Then show the structured conclusion:

- **Root cause:** uplink B packet loss
- **Confidence:** high
- **Blast radius:** Camera 3 only
- **Why not encoder:** CPU/GPU normal
- **Evidence:** linked Grafana observations/deeplinks

This section proves actual sponsor integration.

### 1:15–1:40 — Safe agency

StageGuard proposes:

> Reroute Camera 3 from uplink B to uplink A.

Show:

- action risk tier
- expected impact
- explicit **Approve** / **Reject** controls

Operator approves.

The agent invokes only the allowlisted remediation adapter.

### 1:40–2:05 — Verification

The adapter reports completion, but StageGuard does **not** declare success yet.

It returns to Grafana MCP and checks:

- uplink assignment / relevant state
- Camera 3 frame-drop rate
- packet-loss exposure
- output health

Only then show:

**Incident resolved — recovery verified by telemetry.**

This is the defining agentic loop: **observe → reason → act → verify**.

### 2:05–2:30 — Product credibility

Show the incident evidence trail:

- timestamps
- Grafana evidence links
- action approval
- remediation result
- verification

Then briefly show onboarding/safety controls:

- connect Grafana
- select dashboards/data sources
- map labels
- choose allowed actions
- investigation-only vs controlled-autonomy mode

### 2:30–2:50 — Sponsor reveal

Show Grafana MCP / Agent Observability view if implemented:

- tool calls
- latency
- MCP health
- agent trace/cost information where available

Narration:

“Grafana gives StageGuard eyes into the production. And Grafana gives operators eyes into StageGuard.”

### 2:50–3:00 — Close

Final line:

> **StageGuard doesn't generate the show. It keeps the show on air.**

Show architecture strip:

`Live Production → Grafana → Grafana MCP → Gemini Agent → Human-approved Action → Grafana Verification`

## Minimum proof required before recording

Do not record a fake-looking demo. The following must be real in the permitted implementation:

- actual Gemini/Google agent runtime call path
- actual official Grafana MCP connection
- actual Grafana telemetry query through MCP
- deterministic fault reflected in Grafana
- root-cause output grounded in retrieved evidence
- action approval interaction
- real invocation of safe demo remediation adapter
- post-action Grafana query demonstrating recovery

## Nice-to-have proof

- logs plus metrics instead of metrics only
- Tempo trace evidence
- Grafana Incident/annotation update
- rendered panel evidence
- Grafana MCP/agent observability
- second failure scenario available for judges to test

## Judge mapping

### Technological Implementation

Show that both Google Cloud and Grafana are active runtime dependencies, with a multi-step workflow and verification loop.

### Design

Use an incident cockpit rather than generic chat. Make evidence, approval and current state visually obvious.

### Potential Impact

Frame the user as live broadcast / streaming operations teams where downtime has immediate audience and revenue consequences.

### Quality of Idea

The non-obvious element is applying agentic observability to **live production operations**, with Grafana as both the production evidence plane and the agent-observability plane.

## Demo anti-patterns

Avoid:

- spending 30+ seconds on slides before showing the product
- a prewritten “AI diagnosis” without visible MCP evidence
- claiming a fix worked solely because an action endpoint returned 200
- long chat exchanges
- too many failure types
- showing destructive/unbounded autonomy
- emphasizing AI Observability while failing to show the required Grafana MCP runtime integration

## Backup plan

The hosted demo should have a **Reset Scenario** action that deterministically returns the synthetic production to healthy state, then allows the same failure to be injected again. This is essential for reliable judging.

If any optional service is unavailable during recording, the core flow must still work using metrics + Grafana MCP + safe remediation + verification.
