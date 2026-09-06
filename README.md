# StageGuard

**Autonomous incident commander for live media production.**

StageGuard is a production-oriented Gemini Enterprise / Google Cloud agent that uses Grafana as its live operational evidence layer. It watches a broadcast or production stack, investigates failures across alerts, metrics, logs, traces and dashboards through Grafana MCP, proposes or executes safe remediation, verifies recovery, and leaves an auditable incident trail.

> Product thesis: **Grafana gives Gemini eyes into the production; Gemini turns that evidence into action; Grafana then makes the agent itself observable.**

## Hackathon target

Google Cloud Agentic Cinema — **Grafana Labs track**.

The current rules require a functional, production-ready AI agent powered by Gemini and Google Cloud Agent Builder that solves a media/entertainment bottleneck. For the Grafana track, the project must actively use the Grafana stack at runtime, primarily through the official `grafana/mcp-grafana` server or hosted Grafana Cloud MCP endpoint. Grafana AI Observability is complementary, but does not satisfy the track requirement by itself.

## Problem

Live broadcasts, virtual productions, creator streams and studio pipelines fail under extreme time pressure. Operators already have telemetry, but diagnosis still requires a human to manually correlate many signals while the audience experiences the outage.

A typical incident may involve:

- encoder frame drops
- packet loss or uplink degradation
- audio/video drift
- GPU saturation on render nodes
- CDN/egress latency
- camera or capture-device failures
- failing services in the graphics/control stack

The expensive part is not merely detecting the alert. It is answering, quickly and safely:

1. What actually broke?
2. What else is affected?
3. What evidence supports that diagnosis?
4. What action is safe to take now?
5. Did the action actually fix the issue?

## Product experience

### Incident loop

1. **Trigger** — StageGuard receives an alert or operator request.
2. **Triage** — Gemini identifies the affected production service and initial hypotheses.
3. **Investigate** — the agent calls Grafana MCP tools to inspect alerts, dashboards, metrics, logs and traces.
4. **Correlate** — it builds an evidence-backed root-cause hypothesis and estimates blast radius.
5. **Plan** — it chooses a remediation from an allowlisted action catalog.
6. **Approve when needed** — consequential actions require a human approval step.
7. **Act** — an external remediation adapter performs the permitted operation.
8. **Verify** — StageGuard returns to Grafana and checks whether the relevant telemetry recovered.
9. **Close** — it records the outcome, evidence, timings and residual risk.

### Example judge scenario

A live broadcast is healthy. Camera 3 suddenly begins dropping frames.

StageGuard:

- sees the active alert,
- compares Camera 3 against Cameras 1 and 2,
- checks encoder CPU/GPU metrics,
- inspects network telemetry and related logs,
- identifies packet loss on uplink B as the most likely root cause,
- reports that the blast radius is limited to Camera 3,
- requests approval to reroute Camera 3 to uplink A,
- invokes the demo remediation adapter after approval,
- re-queries Grafana,
- verifies frame-drop and packet-loss metrics have recovered,
- closes the incident with an evidence trail.

## Who this is for

### Primary

- live broadcast operations teams
- streaming/event production teams
- virtual production and LED-stage operators
- creator studios with multi-camera streaming infrastructure

### Secondary

- VFX/render operations teams
- media platform SREs
- sports and esports production crews

## Why Grafana is indispensable

StageGuard is intentionally designed so the sponsor integration cannot be removed without destroying the product:

- **Alerts** provide incident triggers.
- **Prometheus / datasource queries** provide quantitative health evidence.
- **Loki / logs** provide failure context.
- **Tempo / traces** expose dependency-level failures where available.
- **Dashboards and deeplinks** let operators verify agent findings visually.
- **Incidents / annotations** provide an operational record.
- **MCP** makes these capabilities directly callable by the Gemini agent.
- **AI / MCP Observability** can expose the agent's own tool usage, latency and operational behavior.

## Safety model

StageGuard must never be an unconstrained infrastructure agent.

### Autonomy tiers

| Tier | Behavior | Example |
|---|---|---|
| A | Read-only investigation | query metrics/logs/traces |
| B | Reversible low-risk action | restart demo worker / switch synthetic route |
| C | Human-approved action | reroute live feed / fail over service |
| D | Never automated | destructive data/config operations |

The preferred production default is **read-only Grafana access plus separate, tightly scoped remediation adapters**. Grafana MCP tool categories should be restricted to the minimum required capabilities, using least-privilege RBAC.

## Real-user onboarding

A production team should be able to adopt StageGuard without rewriting their monitoring stack.

1. Connect an existing Grafana Cloud workspace or supported Grafana instance.
2. Authenticate through Grafana Cloud MCP OAuth where available, or a least-privilege service account for the OSS MCP server.
3. Select the data sources/dashboards representing production systems.
4. Map telemetry labels into the small StageGuard canonical model (`production`, `service`, `device`, `feed`, `region`, `severity`).
5. Choose allowed remediation actions and approval requirements.
6. Run a dry-run readiness check.
7. Simulate one incident before enabling live use.

No raw production secret should be committed to the repository.

## MVP vertical slice

The winning MVP is deliberately narrow:

**one live-production topology + one injected failure + one evidence-backed diagnosis + one human-approved remediation + one verified recovery.**

Everything else is secondary until this slice works end-to-end.

### Demo topology

- 3 synthetic camera/encoder feeds
- 2 network uplinks
- 1 broadcast output
- Grafana dashboards with production telemetry
- a controlled fault injector
- StageGuard Gemini agent
- Grafana MCP runtime connection
- a reversible remediation adapter

## Success metrics

For the demo/evaluation harness:

- root-cause accuracy on seeded incidents
- correct blast-radius identification
- evidence citation completeness
- mean investigation tool calls
- time-to-diagnosis
- remediation policy compliance
- recovery verification accuracy
- unsafe-action rate (target: 0)

## Repository contract

This repository is currently a **hackathon-safe product and implementation specification**. Submitted implementation code should be produced only with tools permitted by the hackathon rules (for example Gemini CLI / Gemini Code Assist / Google Cloud tooling and allowed Grafana capabilities).

Planned top-level implementation areas for the permitted coding phase:

- `agent/` — Gemini/ADK orchestration
- `integrations/grafana/` — MCP client/configuration boundary
- `integrations/remediation/` — allowlisted demo actions
- `simulator/` — synthetic live-production telemetry + fault injection
- `web/` — operator incident console
- `evals/` — scenario/evidence/safety evaluation

## Submission strategy

The 3-minute demo should prove four things visibly:

1. **real media problem** — a live production degrades;
2. **real Grafana runtime use** — the agent investigates through Grafana MCP;
3. **real agency** — it forms a diagnosis, requests/executes a bounded action and verifies recovery;
4. **real product thinking** — evidence, approvals, observability and safe deployment are coherent.

See `ARCHITECTURE.md`, `DEMO.md` and `progress.md` for the detailed handoff.

## Research / official references

- Hackathon rules: https://agentic-cinema.devpost.com/rules
- Hackathon overview: https://agentic-cinema.devpost.com/
- Grafana MCP introduction: https://grafana.com/docs/grafana/latest/developer-resources/mcp/introduction/
- Grafana MCP tools / RBAC: https://grafana.com/docs/grafana/latest/developer-resources/mcp/reference/mcp-tools-table/
- Grafana Cloud MCP: https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/cloud-mcp/
- Grafana MCP tool restriction/read-only configuration: https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/oss-mcp/configure/enable-and-disable-tools/
- Official Grafana MCP repository: https://github.com/grafana/mcp-grafana
- Grafana AI / Agent Observability positioning: https://grafana.com/ai/
- Grafana MCP Observability: https://grafana.com/docs/grafana-cloud/observe-and-act/monitor-applications/ai-observability/mcp-observability/
- Gemini Enterprise Agent Platform Runtime quickstart: https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime/quickstart-adk

## Status

Specification initialized. **Next implementation gate: prove a permitted Gemini/ADK agent can call official Grafana MCP against a seeded Grafana environment and return an evidence-grounded incident diagnosis.**
