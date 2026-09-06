# StageGuard Vertical Slice Specification

## Purpose

This document defines the **smallest judge-valid runtime slice** StageGuard must prove before any broad UI, remediation, or multi-scenario work begins.

The slice must demonstrate that a Gemini/ADK agent can use the **official Grafana MCP** against real seeded telemetry, retrieve enough evidence to distinguish competing failure hypotheses, and produce a structured diagnosis for a live-media incident.

The implementation itself must be produced with hackathon-permitted Google / partner tooling.

---

## 1. Demo production: `broadcast-alpha`

Use one deterministic synthetic live broadcast with the following topology:

| Entity | Role | Route |
|---|---|---|
| `cam-1` | camera + encoder feed | `uplink-a` |
| `cam-2` | camera + encoder feed | `uplink-a` |
| `cam-3` | camera + encoder feed | `uplink-b` |
| `uplink-a` | healthy primary network path | carries cam-1, cam-2 |
| `uplink-b` | faulted network path | carries cam-3 |
| `program-out` | composed broadcast output | receives all feeds |

All telemetry should include `production_id="broadcast-alpha"` plus relevant `feed_id`, `device_id`, and `uplink` labels.

---

## 2. Seeded incident

### Ground truth

`uplink-b` develops packet loss while `cam-3`'s encoder remains healthy.

### Healthy baseline

For at least several minutes before fault injection:

- all feeds have negligible dropped-frame rate
- both uplinks have negligible packet loss
- encoder CPU/GPU are comfortably below saturation
- output bitrate is stable

### Fault window

Inject a single controlled fault:

- `network_packet_loss_percent{uplink="uplink-b"}` rises to a clearly abnormal value, target ~15–20%
- `video_frames_dropped_total{feed_id="cam-3"}` begins increasing rapidly
- `encoder_cpu_percent{feed_id="cam-3"}` remains normal
- `encoder_gpu_percent{feed_id="cam-3"}` remains normal
- `cam-1` and `cam-2` remain healthy
- `uplink-a` remains healthy

Optional but useful Loki evidence:

- routing/network component emits a concise log such as an uplink degradation / retransmit warning tagged with `uplink="uplink-b"`
- no encoder overload/error log should appear for `cam-3`

The scenario must be resettable and replayable.

---

## 3. Minimum telemetry contract

The first implementation only needs these signals.

### Prometheus metrics

1. `video_frames_dropped_total{production_id,feed_id}`
2. `encoder_cpu_percent{production_id,feed_id}`
3. `encoder_gpu_percent{production_id,feed_id}`
4. `network_packet_loss_percent{production_id,uplink}`
5. `output_bitrate_mbps{production_id}` (optional for Gate A, useful later for verification)

### Loki logs

Optional for the very first connectivity proof, but recommended before the judge demo:

- `production_id`
- `component`
- `feed_id` where relevant
- `uplink` where relevant
- short machine-generated event text

Do not put instructions, secrets, or synthetic prompt-like content in logs.

---

## 4. Exact investigation contract

The agent is given only the incident trigger:

> `Camera 3 is dropping frames in broadcast-alpha. Investigate the root cause and return evidence. Do not remediate.`

The desired investigation order is bounded.

### Step A — confirm symptom

Use official Grafana MCP Prometheus query capability (`query_prometheus`) to establish that `cam-3` is dropping frames during the incident window.

Conceptual PromQL:

```promql
rate(video_frames_dropped_total{production_id="broadcast-alpha",feed_id="cam-3"}[1m])
```

Expected result: clearly elevated dropped-frame rate.

### Step B — test encoder-overload hypothesis

Query CPU and/or GPU for `cam-3`.

Conceptual PromQL:

```promql
encoder_cpu_percent{production_id="broadcast-alpha",feed_id="cam-3"}
```

```promql
encoder_gpu_percent{production_id="broadcast-alpha",feed_id="cam-3"}
```

Expected result: neither is near the seeded overload threshold.

This evidence should **contradict** the encoder-saturation hypothesis.

### Step C — test network hypothesis

Query packet loss by uplink.

Conceptual PromQL:

```promql
network_packet_loss_percent{production_id="broadcast-alpha"}
```

Expected result:

- `uplink-b`: abnormal (~15–20%)
- `uplink-a`: healthy / near zero

### Step D — establish blast radius

Compare dropped-frame rate across all three feeds.

Conceptual PromQL:

```promql
sum by (feed_id) (
  rate(video_frames_dropped_total{production_id="broadcast-alpha"}[1m])
)
```

Expected result: `cam-3` is degraded; `cam-1` and `cam-2` remain healthy.

### Step E — optional log corroboration

Use official Grafana MCP Loki capability (`query_loki_logs`) for the incident window.

Expected result: network/uplink degradation evidence referencing `uplink-b`, with no corresponding encoder-overload evidence.

### Step F — structured diagnosis

The agent should return a machine-readable diagnosis object conceptually containing:

- `incident`: camera 3 frame drops
- `root_cause`: uplink-b packet loss
- `confidence`: high only if evidence threshold is met
- `blast_radius`: cam-3 only
- `supported_hypothesis`: network degradation
- `rejected_hypothesis`: encoder saturation
- `evidence[]`: each item references the Grafana query/tool result and observation window
- `recommended_next_action`: reroute cam-3 to uplink-a
- `action_status`: `NOT_EXECUTED`

The first vertical slice must **not remediate**.

---

## 5. Evidence threshold

A `high` confidence diagnosis requires at least:

1. symptom evidence: elevated dropped frames on `cam-3`
2. causal evidence: elevated packet loss on `uplink-b`
3. contradiction evidence: normal encoder CPU/GPU on `cam-3`
4. peer evidence: `cam-1` / `cam-2` healthy

If one of these classes is missing, downgrade confidence.

If causal and contradiction evidence conflict, return `INCONCLUSIVE` rather than inventing certainty.

---

## 6. Grafana MCP tool policy for Gate A

Current official Grafana MCP documentation exposes `query_prometheus` for Prometheus datasource queries and `query_loki_logs` for Loki queries. `run_panel_query` can later execute an existing dashboard panel query but is disabled by default and is not required for the first gate.

For the first slice, expose only the minimum useful read-side categories/tools.

### Required

- Prometheus query capability
- datasource discovery only if needed for setup

### Recommended before demo

- Loki query capability
- dashboard search/read or deeplink capability

### Explicitly unnecessary for Gate A

- dashboard writes
- alert-rule writes
- incident writes
- annotation writes
- admin tools
- remediation through Grafana

Use read-only posture where compatible. Keep datasource scope limited to the seeded Prometheus/Loki sources.

Current official reference indicates `query_prometheus` and `query_loki_logs` require `datasources:query` with datasource-specific scope such as `datasources:uid:<uid>`.

---

## 7. Connectivity / security acceptance

The implementation handoff should not consider MCP “connected” until all of the following are recorded:

- chosen mode: hosted Grafana Cloud MCP **or** official OSS `grafana/mcp-grafana`
- authentication mechanism used
- Grafana instance/workspace identifier (non-secret)
- MCP transport used
- datasource UIDs used (non-secret)
- enabled tool categories
- read/write restrictions
- minimum RBAC grants
- one successful real MCP tool call
- one intentionally denied/unavailable write capability where practical, proving least privilege

No tokens, client secrets, service-account secrets, or OAuth credentials may enter the repo.

---

## 8. Gate A — eligibility vertical slice

**Goal:** prove real sponsor integration and evidence-grounded reasoning.

Pass only if:

1. a permitted Gemini/ADK runtime invokes the **official Grafana MCP**
2. MCP queries the real seeded Grafana datasource
3. at least two real telemetry lookups occur; target four evidence classes above
4. the diagnosis identifies `uplink-b` packet loss
5. encoder overload is explicitly rejected using retrieved evidence
6. blast radius identifies `cam-3` while healthy peers remain unaffected
7. returned diagnosis includes evidence references / query context
8. no remediation is executed
9. the scenario can be reset and reproduced

Any hard-coded diagnosis fails this gate even if the text is correct.

---

## 9. Gate B — judge-ready investigation

After Gate A passes, add:

- incident trigger from Grafana alert or a clearly simulated alert event
- Loki corroboration
- Grafana dashboard/deeplink evidence shown to operator
- evidence ledger persisted for the incident
- timing/tool-call trace visible in UI or logs
- negative `INCONCLUSIVE` fixture proving safe refusal under ambiguous data

Only after Gate B should remediation be implemented.

---

## 10. Gate C — approval, remediation, verification

The primary judge action is:

`reroute_feed(feed_id="cam-3", target_uplink="uplink-a")`

Requirements:

- action comes from an allowlist
- argument validation
- explicit human approval
- idempotency key / duplicate-action protection
- simulator state changes route only
- agent re-queries Grafana after action
- incident resolves only when telemetry proves dropped frames and packet loss recovered

A successful action API response alone is **not** recovery.

---

## 11. Judge-visible evidence

During the 3-minute demo, make these five facts visually undeniable:

1. Camera 3 is actually degraded.
2. Gemini is actually invoking Grafana MCP rather than reading hard-coded values.
3. Grafana evidence distinguishes network fault from encoder fault.
4. A human controls the consequential action.
5. Grafana verifies the recovery after the action.

If time permits, finish by showing Grafana MCP / agent observability so Grafana visibly monitors the same agent that is using Grafana to monitor the production.

---

## 12. Implementation order for permitted Gemini tooling

1. create deterministic simulator telemetry
2. connect Prometheus datasource to Grafana
3. prove Grafana shows the seeded metrics
4. connect official Grafana MCP with least privilege
5. prove direct MCP `query_prometheus` call
6. connect MCP tools to Gemini/ADK
7. implement bounded investigation policy
8. return structured diagnosis + evidence
9. add Loki corroboration and Grafana links
10. add negative `INCONCLUSIVE` fixture
11. only then build approval/remediation/verification
12. build incident cockpit after runtime slice is stable

---

## 13. Current official references

- Grafana MCP introduction: https://grafana.com/docs/grafana/latest/developer-resources/mcp/introduction/
- Grafana MCP tools/RBAC: https://grafana.com/docs/grafana/latest/developer-resources/mcp/reference/mcp-tools-table/
- Grafana MCP tool restriction/read-only controls: https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/oss-mcp/configure/enable-and-disable-tools/
- Running dashboard panel queries through MCP: https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/oss-mcp/guides/run-a-dashboard-panel-query/
- Official MCP implementation: https://github.com/grafana/mcp-grafana

Tool names and defaults should be re-verified against the exact version/environment used during implementation.