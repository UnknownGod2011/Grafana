# StageGuard Architecture

## 1. Architectural goal

StageGuard should behave like a **bounded autonomous incident commander** for live media systems. It must use Grafana as the primary operational evidence layer, keep all consequential actions policy-controlled, and leave a traceable record of what it observed, inferred, proposed and verified.

The architecture deliberately separates **observation** from **remediation**:

- Grafana MCP is the agent's evidence surface.
- Gemini/ADK handles reasoning and orchestration.
- Remediation occurs through a small allowlisted adapter layer, not arbitrary shell/cloud access.

This separation makes the system safer and makes the sponsor integration clearer to judges.

---

## 2. Logical topology

```text
Production systems / simulator
        |
        | telemetry (OTel / metrics / logs / traces)
        v
Grafana Cloud / Grafana stack
  - dashboards
  - alerts
  - metrics
  - logs
  - traces
  - incidents / annotations
        |
        | official Grafana MCP
        v
StageGuard Agent (Gemini + Google ADK / Agent Platform Runtime)
  - incident state machine
  - investigation planner
  - evidence ledger
  - root-cause reasoning
  - policy gate
  - verification loop
        |
        +----------------------+
        |                      |
        v                      v
Operator Web Console      Remediation Adapter
  - incident summary       - explicit action catalog
  - evidence trail         - scoped credentials
  - approve/reject         - reversible demo actions
  - telemetry links        - idempotent execution
        |                      |
        +----------+-----------+
                   |
                   v
              affected system
                   |
                   v
          verification via Grafana MCP
```

---

## 3. Runtime components

### 3.1 Production telemetry source

The real product should consume existing telemetry rather than forcing a proprietary monitoring agent.

For the hackathon demo, use a deterministic synthetic media topology so the failure can be reproduced reliably:

- camera/encoder A, B, C
- uplink A, B
- broadcast mux/output
- optional graphics/render service

Each component emits canonical dimensions:

- `production_id`
- `environment`
- `service`
- `device_id`
- `feed_id`
- `uplink`
- `region`
- `severity`

Useful signal families:

- `video_frames_total`
- `video_frames_dropped_total`
- `encoder_fps`
- `encoder_cpu_percent`
- `encoder_gpu_percent`
- `network_packet_loss_percent`
- `network_rtt_ms`
- `audio_video_drift_ms`
- `output_bitrate_mbps`
- service request/error/latency telemetry where applicable

The exact metric names may differ in implementation; the important design choice is a small stable semantic contract.

### 3.2 Grafana layer

Grafana is the operational source of truth.

Minimum hackathon capabilities:

1. active alert discovery
2. metrics queries
3. log queries
4. dashboard/deeplink retrieval
5. annotations or incident record where practical

High-value optional capabilities:

- traces / Tempo for dependency diagnosis
- Sift/investigation primitives
- Grafana Incident
- rendered dashboard/panel evidence
- agent/MCP observability

**Requirement:** the submitted runtime must make genuine calls through the official `grafana/mcp-grafana` server or hosted Grafana Cloud MCP endpoint. AI Observability alone is insufficient under the current rules.

### 3.3 StageGuard agent

Preferred runtime: Gemini model orchestrated with Google ADK and deployed to Gemini Enterprise Agent Platform Runtime where feasible.

Internal responsibilities:

- normalize incident trigger
- identify relevant topology/entities
- create investigation hypotheses
- select Grafana MCP tools
- record structured evidence
- score root-cause confidence
- assess blast radius
- select a remediation candidate
- apply safety policy
- request human approval if required
- invoke remediation adapter
- re-query Grafana to verify outcome
- produce final incident summary

### 3.4 Evidence ledger

Do not let the agent jump directly from tool output to a free-form conclusion. Maintain a small structured incident evidence object.

Each evidence item should conceptually include:

- source type: metric / log / trace / alert / dashboard
- Grafana resource or query reference
- observation timestamp/window
- entity affected
- normalized observation
- hypothesis supported/contradicted
- confidence contribution

A root-cause statement shown to the operator should be backed by at least two independent observations when possible.

### 3.5 Operator console

The web app is not a generic chatbot. It is an **incident cockpit**.

Primary view:

- incident title + severity
- current production health
- root-cause hypothesis + confidence
- blast radius
- evidence timeline
- Grafana deeplinks
- proposed remediation
- approval button when needed
- post-action verification
- final incident status

A free-text operator instruction box can exist, but should be secondary.

### 3.6 Remediation adapter

The agent should never receive arbitrary infrastructure credentials.

Expose an allowlisted catalog such as:

- `reroute_feed(feed_id, target_uplink)`
- `restart_demo_encoder(device_id)`
- `switch_backup_output(output_id)`
- `throttle_optional_graphics(service_id)`

For the hackathon demo these actions can target a simulator. The architectural contract should be production-realistic:

- explicit action IDs
- validated arguments
- idempotency key
- timeout
- rollback or reverse action where possible
- action audit result
- no general shell execution

---

## 4. Incident state machine

```text
DETECTED
  -> TRIAGING
  -> INVESTIGATING
  -> DIAGNOSIS_READY
  -> ACTION_PROPOSED
  -> WAITING_APPROVAL   (when required)
  -> REMEDIATING
  -> VERIFYING
  -> RESOLVED

Failure exits:
  -> INCONCLUSIVE
  -> ACTION_FAILED
  -> ESCALATED
```

Important rule: **the agent may not mark an incident resolved merely because an action API returned success.** Resolution requires telemetry-based verification through Grafana.

---

## 5. Deterministic investigation policy

To keep the workflow judgeable and safe, use a bounded evidence-first sequence rather than unconstrained agent wandering.

### Phase A — establish symptom

- fetch alert context
- inspect affected entity's key health metric
- define incident time window

### Phase B — compare

- compare affected feed/device against healthy peers
- compare pre-incident baseline vs incident window

### Phase C — correlate

- inspect upstream/downstream component telemetry
- query relevant logs
- inspect trace dependency evidence when available

### Phase D — decide

- rank candidate root causes
- require minimum evidence/confidence threshold
- estimate blast radius

### Phase E — remediate safely

- map root cause to an allowlisted action
- run policy gate
- request approval based on tier

### Phase F — verify

- re-run the key symptom and causal metrics
- compare against recovery thresholds
- close only if telemetry proves improvement

This gives the product a strong answer to “what makes it deterministic?” while still allowing Gemini to reason over real evidence.

---

## 6. Safety and permissions

### Grafana access

Use the minimum necessary MCP tool categories and RBAC scopes.

Recommended deployment posture:

- read-only Grafana permissions for investigation by default
- enable only required MCP tool groups
- separate write-capable incident/annotation access if used
- avoid broad Editor permissions in production unless unavoidable
- secrets stored outside source control
- prefer Grafana Cloud MCP OAuth 2.1 where the hosted path fits

For OSS `mcp-grafana`, use a service account token with granular permissions. Do not expose MCP directly to browsers.

### Action policy

Every action definition needs:

- allowed target class
- risk tier
- preconditions
- required approval class
- rollback capability
- max frequency / cooldown
- verification metric

### Prompt-injection boundary

Telemetry/log content is untrusted data. Treat text returned from logs as evidence, never as agent instructions. Tool output cannot elevate privileges or change the safety policy.

### Sensitive telemetry

Agent traces, log content and MCP arguments may contain operational or user data. In production:

- avoid exporting raw sensitive arguments
- redact secrets/PII before LLM context
- scope incident windows tightly
- follow Grafana guidance before enabling tool-argument capture in traces

---

## 7. Agent observability

StageGuard should be observable in two layers:

### Google runtime telemetry

Gemini Enterprise Agent Platform Runtime currently supports ADK telemetry, including OpenTelemetry-aligned generative-AI metrics for supported ADK versions.

### Grafana AI / MCP observability

Use Grafana to demonstrate:

- MCP connection health
- tool invocation frequency
- tool latency/failures
- agent execution traces where configured
- possibly token/cost/conversation observability through Grafana AI Observability

This creates the demo's strongest sponsor loop:

> StageGuard uses Grafana to understand the production, and Grafana lets operators understand StageGuard.

---

## 8. Deployment topology

### Hackathon/demo

- web operator console: web-hosted app
- Gemini/ADK agent: Google Cloud / Agent Platform Runtime if feasible
- simulator: safe hosted or local deterministic service
- Grafana: Grafana Cloud workspace or supported Grafana instance
- MCP: hosted Grafana Cloud MCP where compatibility is proven; otherwise official `grafana/mcp-grafana`
- remediation adapter: isolated demo service with no production privileges

### Production target

- tenant-specific Grafana authorization
- agent identity / workload identity
- central StageGuard policy service
- tenant-scoped remediation connectors
- immutable audit trail
- optional incident-management integration

---

## 9. Real-world onboarding model

The product should support two onboarding modes.

### Mode 1 — fast proof of value

A team connects Grafana, selects existing dashboards/data sources and maps a handful of labels. StageGuard initially runs in **investigation-only mode** and generates incident diagnoses without taking actions.

### Mode 2 — controlled autonomy

After trust is established, the team configures remediation adapters and approval policy per action type.

This creates a credible enterprise adoption curve:

**observe -> recommend -> approve -> selectively automate**.

---

## 10. Demo scenarios

### Primary: uplink packet loss

Symptom: Camera 3 frame-drop alert.

Evidence chain:

- dropped frames rise only on Camera 3
- encoder CPU/GPU remain normal
- uplink B packet loss spikes
- Camera 3 is routed through uplink B
- healthy cameras use uplink A

Action: reroute Camera 3 to uplink A after operator approval.

Verification:

- packet loss / frame-drop recover
- output bitrate stabilizes
- alert transitions toward healthy state

### Secondary: encoder saturation

Symptom: frame drops on one feed.

Evidence:

- GPU utilization near saturation
- thermal or resource log signal
- network remains healthy

Action: restart/switch backup encoder in demo environment.

### Negative test: ambiguous evidence

Metrics conflict or insufficient data.

Expected behavior: StageGuard refuses to remediate and escalates as **INCONCLUSIVE**.

This negative scenario is important evidence that the system is not just an autonomous action demo.

---

## 11. Evaluation harness

Create deterministic scenario fixtures during permitted implementation.

For each scenario specify:

- ground-truth root cause
- affected entities
- telemetry pattern
- allowed actions
- expected approval tier
- expected verification metrics

Score:

- diagnosis correctness
- blast radius correctness
- evidence relevance
- action selection correctness
- policy compliance
- verification correctness
- time/tool-call efficiency

The demo should prioritize correctness and auditable reasoning over open-ended conversational cleverness.

---

## 12. Implementation order for Gemini coding phase

### P0 — eligibility vertical slice

1. seed Grafana with one deterministic production scenario
2. establish official Grafana MCP connectivity
3. build Gemini/ADK tool invocation path
4. prove metric/log lookup through MCP at runtime
5. return evidence-grounded diagnosis

### P1 — agentic incident loop

6. incident state machine
7. evidence ledger
8. blast-radius reasoning
9. allowlisted remediation adapter
10. human approval
11. post-action telemetry verification

### P2 — product experience

12. incident cockpit web UI
13. Grafana deeplinks/evidence timeline
14. onboarding flow
15. agent/MCP observability view

### P3 — submission polish

16. deterministic demo scenario
17. evaluation fixtures
18. security/readme/runbook
19. hosted deployment
20. 3-minute demo recording

---

## 13. Explicit non-goals for MVP

Do not spend hackathon time on:

- arbitrary cloud remediation
- dozens of media protocols
- generic chatbot UX
- custom observability backend
- replacing Grafana dashboards
- autonomous destructive actions
- full enterprise multi-tenancy before the core demo works

---

## 14. Key technical references

- Hackathon rules: https://agentic-cinema.devpost.com/rules
- Grafana MCP: https://github.com/grafana/mcp-grafana
- Grafana MCP intro: https://grafana.com/docs/grafana/latest/developer-resources/mcp/introduction/
- Grafana MCP RBAC/tools: https://grafana.com/docs/grafana/latest/developer-resources/mcp/reference/mcp-tools-table/
- Grafana Cloud MCP: https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/cloud-mcp/
- MCP tool restriction/read-only: https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/oss-mcp/configure/enable-and-disable-tools/
- MCP observability: https://grafana.com/docs/grafana-cloud/observe-and-act/monitor-applications/ai-observability/mcp-observability/
- Grafana AI: https://grafana.com/ai/
- Agent Platform Runtime: https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime/quickstart-adk
