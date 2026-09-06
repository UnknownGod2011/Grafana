# StageGuard Integration Handoff

## Purpose

This document removes the remaining setup ambiguity before hackathon-permitted implementation begins. It defines the recommended first Grafana MCP deployment mode, the exact environment contract, the evidence that must be captured for judging, and the path from the deterministic demo to a real-user installation.

No submitted application code is defined here; implementation should be produced with hackathon-permitted Google / partner tooling.

---

## 1. Recommended first implementation path

### Default for the hackathon vertical slice: OSS `grafana/mcp-grafana`

Use the official open-source Grafana MCP server against a local or otherwise already-available Grafana instance for the first deterministic Gate A proof.

Why this is the preferred first path:

1. **No paid service needs to be enabled merely to prove MCP connectivity.**
2. The implementation can use a narrowly scoped Grafana service-account token rather than introducing an interactive OAuth dependency into the first judge-critical runtime slice.
3. OSS MCP supports the transports needed for local development, including stdio and Streamable HTTP.
4. The same official tool surface remains portable to Grafana Cloud later.
5. It gives the team full control over resettable seeded Prometheus/Loki demo data.

### Production/onboarding path: Grafana Cloud MCP where appropriate

For real Grafana Cloud users, the hosted Grafana Cloud MCP is the lower-friction onboarding target:

- fully hosted by Grafana
- OAuth 2.1 authorization
- Streamable HTTP transport
- user-scoped access inherited from Grafana RBAC
- read-only access can be selected during authorization
- no local MCP installation required

This should be presented as the real-user path, not as a required dependency for the first demo.

### Important billing/usage note

Current Grafana documentation states that Cloud MCP is part of Grafana Assistant and connected users count toward Assistant usage. Therefore StageGuard should **not automatically provision or enable a paid Grafana Cloud capability** during setup. The product should detect/configure an existing user-provided environment and clearly disclose any provider-side usage implications.

Official reference: https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/cloud-mcp/

---

## 2. Gate A environment contract

The first implementation should freeze the following topology unless runtime evidence proves a change is necessary:

```text
Synthetic broadcast simulator
        |
        +--> Prometheus-compatible metrics endpoint
        |
        +--> optional structured logs
                    |
                    v
              Grafana instance
              /            \
     Prometheus datasource  Loki datasource (Gate B)
              |
              v
     official mcp-grafana
              |
              v
       Gemini / ADK agent
```

### Minimum components

- one Grafana instance
- one Prometheus-compatible datasource containing `broadcast-alpha` telemetry
- official `grafana/mcp-grafana`
- one least-privilege service account/token for OSS MCP
- one Gemini/ADK runtime permitted by hackathon rules

### Do not require for Gate A

- Grafana Cloud
- Loki
- Tempo
- Grafana alert-rule writes
- incident writes
- remediation writes
- AI Observability
- public hosting

These are upgrades after sponsor-critical connectivity works.

---

## 3. MCP transport decision

### Local proof

Prefer **stdio** when Gemini/ADK's selected MCP client path supports it cleanly and the MCP server runs beside the agent.

Advantages:

- minimal network surface
- no separate HTTP listener
- simple local deterministic testing

### Hosted/containerized proof

Prefer **Streamable HTTP** when the agent and MCP server run as separate services.

Current official Grafana documentation confirms the OSS server supports stdio, SSE and Streamable HTTP, while Grafana Cloud MCP uses Streamable HTTP and does not support SSE.

The final repo must record which mode was actually used rather than claiming both.

Official references:

- https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/oss-mcp/set-up/
- https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/oss-mcp/set-up/install-with-docker/
- https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/cloud-mcp/

---

## 4. Authentication and least privilege

### OSS MCP

Use a dedicated Grafana service account for StageGuard. Never reuse an administrator token.

Gate A needs only enough access to:

- identify/query the seeded Prometheus datasource
- optionally query Loki later
- optionally read/search relevant dashboards later

Current Grafana MCP reference documents datasource-query permissions and datasource-scoped RBAC. The actual token permissions used in the implementation must be recorded after runtime verification.

### Grafana Cloud MCP

For production onboarding, prefer OAuth 2.1 and request/read-enable only the capabilities StageGuard needs. Current Grafana Cloud MCP authorization allows read access without granting write access.

### Secret handling

Never commit:

- Grafana service-account tokens
- OAuth access/refresh tokens
- Google Cloud credentials
- MCP auth headers

The README should expose variable names / setup placeholders only after permitted implementation determines the exact configuration surface.

---

## 5. Judge-proof runtime evidence package

A correct diagnosis is not enough. The implementation must make sponsor runtime usage undeniable.

For every demo incident, capture a compact evidence ledger containing:

| Field | Required evidence |
|---|---|
| incident ID | stable synthetic incident identifier |
| trigger time | incident start timestamp |
| MCP server | official Grafana MCP mode/version if available |
| tool calls | actual tool names invoked |
| datasource | non-secret datasource UID/name |
| queries | PromQL/LogQL or equivalent query context |
| observations | normalized result summary |
| hypotheses | supported/rejected hypotheses |
| diagnosis | root cause + confidence |
| blast radius | affected/unaffected feeds |
| latency | investigation start → diagnosis |
| action | none for Gate A; approval state for Gate C |
| verification | post-action Grafana evidence for Gate C |

### Demo UI principle

Do not show raw chain-of-thought. Show **observable agent actions and retrieved evidence**:

- "Queried cam-3 dropped-frame rate"
- "Checked encoder CPU/GPU"
- "Compared packet loss across uplinks"
- "Compared peer camera health"
- "Root cause: uplink-b packet loss"

This is both clearer to judges and safer than presenting hidden reasoning.

---

## 6. Exact Gate A judge card

The first judge-facing result should be renderable as one compact card:

**Incident**
Camera 3 frame drops — `broadcast-alpha`

**Diagnosis**
`uplink-b` packet loss

**Confidence**
High

**Evidence**

1. cam-3 dropped-frame rate elevated
2. uplink-b packet loss elevated (~15–20%)
3. cam-3 encoder CPU/GPU normal
4. cam-1 and cam-2 healthy

**Rejected hypothesis**
Encoder saturation

**Recommended action**
Reroute cam-3 to uplink-a

**Status**
Not executed — approval required

A judge should be able to click/open evidence into Grafana where possible.

---

## 7. Real-user onboarding contract

The product should eventually support two explicit connection modes rather than pretending every customer runs the same stack.

### Mode A — Grafana Cloud

1. User chooses **Connect Grafana Cloud**.
2. StageGuard opens the hosted Cloud MCP OAuth flow.
3. User grants read-only access initially.
4. StageGuard discovers permitted datasources/dashboards.
5. User maps production labels/entities into StageGuard's canonical model.
6. Readiness test executes harmless queries.
7. StageGuard displays exactly what it can and cannot access.
8. User runs one dry-run incident before enabling live alert intake.

### Mode B — self-hosted / existing Grafana

1. User deploys official `grafana/mcp-grafana` near their environment.
2. User creates a dedicated least-privilege service account.
3. User supplies endpoint/transport and secret through deployment configuration, never through source control.
4. StageGuard performs a capability/readiness test.
5. User maps telemetry labels and dashboards.
6. Dry-run incident validates evidence quality.

### Readiness checks

Before calling a connection "ready," StageGuard should verify:

- MCP endpoint/server reachable
- required query tool available
- required datasource readable
- one known health query succeeds
- write capability absent or disabled in investigation-only mode
- expected production labels exist
- timestamp/window semantics are correct

---

## 8. Telemetry mapping model

Real users will not use StageGuard's synthetic metric names. Do not make production adoption depend on renaming their metrics.

Use a lightweight mapping layer conceptually containing:

- canonical concept: `dropped_frames`
- datasource UID
- query template
- required variables/labels
- healthy threshold / expected range
- unit
- entity association (`feed`, `uplink`, `encoder`, `program-output`)

Example conceptual mapping:

```text
canonical: dropped_frames
query: rate(my_vendor_encoder_dropped_frames_total{channel="$feed"}[1m])
entity label: channel
unit: frames/sec
```

The demo can use fixed canonical metrics, while the real product supports mapping to existing telemetry.

---

## 9. Safety boundary for remediation

Grafana remains the evidence plane. Remediation remains a separate action plane.

Never give the agent broad infrastructure credentials merely because it can read Grafana.

Every remediation adapter should define:

- action name
- schema-validated arguments
- allowed target set
- autonomy tier
- approval requirement
- idempotency semantics
- timeout
- rollback/reversal behavior
- verification query

For the hackathon demo, the only required action is the reversible synthetic reroute:

`reroute_feed(cam-3, uplink-a)`

No arbitrary shell execution is needed or desirable.

---

## 10. Observability-of-the-agent reveal

After Gate B/C is stable, add the sponsor "double reveal":

1. StageGuard uses Grafana MCP to observe the broadcast.
2. Grafana observes StageGuard's own MCP behavior.

Current Grafana MCP observability documentation exposes protocol/session health, tool invocation analytics, latency, failures and transport performance. The OSS MCP server can expose Prometheus metrics over HTTP transports and export traces/logs through OpenTelemetry.

That creates a strong closing visual for the demo without being required for eligibility.

Official references:

- https://grafana.com/docs/grafana-cloud/observe-and-act/monitor-applications/ai-observability/mcp-observability/
- https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/oss-mcp/developer/observability-metrics-and-tracing/

---

## 11. Production evolution after hackathon

The architecture should naturally expand in this order:

1. investigation-only for one live-production service
2. alerts as autonomous triggers
3. evidence links and incident history
4. multiple incident fixtures/evals
5. human-approved reversible actions
6. selective automatic actions with policy thresholds
7. logs/traces correlation
8. user-defined telemetry mappings
9. multi-site / multi-show routing
10. incident learning from verified historical outcomes

Do not start with broad autonomous remediation.

---

## 12. Implementation evidence checklist

When permitted implementation begins, update this document or `progress.md` with actual values for:

- [ ] Grafana version/environment
- [ ] MCP implementation/version
- [ ] MCP transport
- [ ] auth mechanism
- [ ] service-account/RBAC posture (non-secret)
- [ ] Prometheus datasource UID/name
- [ ] actual available MCP tools
- [ ] actual `query_prometheus` request/result shape
- [ ] successful known-health query
- [ ] successful incident query
- [ ] intentionally unavailable/denied write behavior
- [ ] total MCP calls for Gate A
- [ ] Gate A diagnosis latency
- [ ] reproducibility/reset result

Runtime observations override assumptions in this document.

---

## 13. Current official references checked 2026-09-06

- Grafana Cloud MCP server: https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/cloud-mcp/
- OSS MCP setup: https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/oss-mcp/set-up/
- OSS MCP Docker setup: https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/oss-mcp/set-up/install-with-docker/
- MCP tools/RBAC reference: https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/oss-mcp/reference/mcp-tools-table/
- MCP Observability: https://grafana.com/docs/grafana-cloud/observe-and-act/monitor-applications/ai-observability/mcp-observability/
- MCP server metrics/tracing/log export: https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/oss-mcp/developer/observability-metrics-and-tracing/
- Official implementation: https://github.com/grafana/mcp-grafana
