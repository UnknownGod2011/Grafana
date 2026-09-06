# StageGuard Progress

## Current status

StageGuard has moved from an empty repository to an implementation-ready product/architecture specification for the Grafana track of Google Cloud Agentic Cinema.

**Current implementation gate:** prove the smallest real runtime slice using hackathon-permitted tooling:

`Gemini/ADK → official Grafana MCP → seeded live-production telemetry → evidence-grounded diagnosis`

Do not build broad UI or multiple scenarios before this works.

The runtime handoff is now concretely specified in `VERTICAL_SLICE_SPEC.md` rather than left as a generic connectivity task.

---

## Run log — 2026-09-06 — initial specification

### Inspected at start

- Repository `UnknownGod2011/grafana` was empty.
- No `progress.md`, README, architecture, source code, CI or other files existed.
- Therefore the first run initialized the specification rather than attempting to extend nonexistent work.

### Research completed

Verified against current official sources:

1. **Hackathon requirement:** the Grafana-track submission must actively use the Grafana stack at runtime, primarily through the official `grafana/mcp-grafana` server or hosted Grafana Cloud MCP endpoint. Grafana AI Observability is complementary but does not satisfy the track requirement alone.
2. **Grafana MCP surface:** supports observability workflows including metrics, logs, traces, dashboards, alerts, incidents, investigations and deeplinks, with tool availability dependent on configuration/product capabilities.
3. **Safety controls:** Grafana MCP can restrict enabled tool categories and can run with write operations disabled; Grafana documents per-tool RBAC requirements/scopes.
4. **Cloud onboarding option:** Grafana Cloud MCP is hosted and uses OAuth 2.1, while the OSS MCP server can use a Grafana service-account token.
5. **MCP observability:** Grafana can expose MCP health, tool usage, latency and failure analytics.
6. **Agent runtime:** current Gemini Enterprise Agent Platform docs support ADK deployment on Agent Platform Runtime; current release notes describe OpenTelemetry-aligned ADK telemetry support.
7. **Official OSS reference:** `grafana/mcp-grafana` is the implementation reference to study during the permitted coding phase.

### Files created

- `README.md` — product thesis, target users, workflow, sponsor dependency, onboarding, safety and MVP.
- `ARCHITECTURE.md` — topology, telemetry contract, evidence ledger, bounded agent policy, RBAC, remediation separation and deployment plan.
- `DEMO.md` — deterministic three-minute judge narrative.
- `progress.md` — persistent run handoff.

### Decisions locked

1. Primary use case is live production/broadcast incident response, not generic application SRE.
2. Primary demo failure is Camera 3 frame drops caused by uplink-B packet loss.
3. Grafana is the operational evidence source before and after remediation.
4. Grafana investigation and remediation are separated; StageGuard does not get arbitrary shell/cloud access.
5. Rerouting a live feed is human-approved in the demo.
6. Resolution requires Grafana telemetry verification.
7. UX is an incident cockpit, not chatbot-first.
8. Adoption path is investigation-only → recommendations → human-approved actions → selective autonomy.
9. One excellent vertical slice comes before additional failure types.

---

## Run log — 2026-09-06 — vertical slice contract

### Inspected at start

Read `progress.md`, `README.md`, and `ARCHITECTURE.md` before making changes. The repo already had a strong product/architecture thesis, but the highest-priority blocker was that the P0 runtime gate still left too many implementation decisions implicit: seeded metric names, exact evidence sequence, expected query results, confidence threshold, minimum Grafana permissions, and objective pass/fail criteria were not yet frozen.

### Fresh official research

Re-checked current Grafana documentation on 2026-09-06 and confirmed:

1. Official Grafana MCP currently exposes `query_prometheus` for Prometheus datasource queries and `query_loki_logs` for Loki queries.
2. Those query tools require `datasources:query` plus an appropriate datasource scope; current docs show datasource-specific scope patterns such as `datasources:uid:<uid>`.
3. Grafana MCP supports broad dashboard/data-source/alert/incident capabilities, but the first StageGuard gate does not need writes.
4. The server supports tool restriction and read-only posture. `--disable-write` removes write operations; query execution can be controlled separately.
5. `run_panel_query` is useful later for replaying the exact query behind an existing Grafana panel, but is disabled by default and is not required for Gate A.

Official references recorded in `VERTICAL_SLICE_SPEC.md`:

- https://grafana.com/docs/grafana/latest/developer-resources/mcp/introduction/
- https://grafana.com/docs/grafana/latest/developer-resources/mcp/reference/mcp-tools-table/
- https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/oss-mcp/configure/enable-and-disable-tools/
- https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/oss-mcp/guides/run-a-dashboard-panel-query/
- https://github.com/grafana/mcp-grafana

### New file: `VERTICAL_SLICE_SPEC.md`

This converts the P0 goal into a deterministic implementation handoff.

It now freezes:

- demo production ID: `broadcast-alpha`
- `cam-1`, `cam-2`, `cam-3`, `uplink-a`, `uplink-b`, `program-out` topology
- ground-truth incident: packet loss on `uplink-b`, with `cam-3` frame drops and normal encoder CPU/GPU
- minimum metric contract:
  - `video_frames_dropped_total`
  - `encoder_cpu_percent`
  - `encoder_gpu_percent`
  - `network_packet_loss_percent`
  - optional verification metric `output_bitrate_mbps`
- optional Loki corroboration contract
- bounded investigation sequence
- conceptual PromQL for symptom, encoder hypothesis, network hypothesis and peer/blast-radius comparison
- expected evidence for each query
- structured diagnosis fields
- high-confidence evidence threshold
- explicit `INCONCLUSIVE` behavior when evidence conflicts
- minimum Grafana MCP tool/RBAC posture
- connectivity/security facts that must be recorded during implementation
- Gate A: eligibility/runtime proof
- Gate B: judge-ready investigation
- Gate C: approval/remediation/verification
- judge-visible evidence requirements
- exact implementation order for permitted Gemini tooling

### Decisions locked this run

1. **Gate A is diagnosis-only.** No remediation until sponsor runtime integration and evidence-grounded diagnosis are proven.
2. **Four evidence classes define a high-confidence root cause:** symptom, causal network evidence, contradiction of encoder overload, and healthy-peer/blast-radius evidence.
3. **Hard-coded diagnosis fails Gate A**, even if the output text is correct.
4. **Prometheus is the minimum required data path.** Loki is recommended for the final demo but not allowed to block the first connectivity proof.
5. **The P0 MCP posture is least-privilege and read-side only.** Dashboard/incident/admin writes are unnecessary.
6. **`run_panel_query` is an optimization for judge-facing dashboard parity, not a Gate A dependency.**
7. **The runtime implementation must record its exact MCP mode, auth method, transport, datasource UIDs, enabled tools and RBAC without committing secrets.**

### Why this is meaningful progress

The next permitted implementation session no longer needs to invent a simulator schema or decide what evidence constitutes success. It can implement one fixed scenario and objectively determine whether the sponsor-critical runtime slice passes.

---

## Current blockers / unknowns

1. **No submitted implementation exists yet.** This remains intentional because OpenAI tooling must not generate hackathon implementation artifacts under the stated rules; use Gemini CLI/Gemini Code Assist / permitted Google tooling for implementation.
2. **Grafana environment is not provisioned/connected yet.** Choose hosted Grafana Cloud MCP or official OSS `mcp-grafana` based on the fastest reliable permitted implementation path.
3. **Google Cloud project/runtime is not connected yet.** Need permitted Gemini/ADK runtime setup.
4. **No deterministic telemetry simulator exists yet.** Its exact first scenario is now specified in `VERTICAL_SLICE_SPEC.md`.
5. **No Grafana dashboards/alerts/data sources exist yet.** They must be created during the permitted implementation/setup phase.
6. **No remediation adapter exists yet.** It should initially manipulate only synthetic routing state and must wait until Gate B passes.
7. **No LICENSE file exists.** The official rules require the public repo to include a detectable open-source license before submission; license choice is not yet locked.
8. **Hosted project URL and demo assets do not exist yet.**
9. **Exact MCP tool names/defaults must still be verified against the version/environment actually deployed.** Current docs were checked on 2026-09-06, but implementation evidence wins over documentation assumptions.

## Risks to watch

- Sponsor integration becomes cosmetic instead of visible in the actual runtime path.
- UI/dashboard polish starts before MCP connectivity works.
- Agent reaches a plausible diagnosis without enough retrieved evidence.
- Metric names diverge from the fixed demo contract without updating the spec.
- Demo remediation is declared successful without telemetry verification.
- Permissions are broader than necessary.
- Optional Grafana AI Observability distracts from required core MCP use.
- Demo relies on nondeterministic external failures.
- More scenarios/features are added before the core one is resettable and replayable.

---

## Single best next step

**Using hackathon-permitted Google tooling, implement Gate A exactly as defined in `VERTICAL_SLICE_SPEC.md`: seed the `broadcast-alpha` Prometheus telemetry, connect the official Grafana MCP with datasource-scoped read/query permissions, and prove Gemini/ADK retrieves the four evidence classes needed to diagnose `uplink-b` packet loss and reject encoder overload.**

Before doing UI work, record these implementation facts in the repo:

- chosen MCP mode (Grafana Cloud hosted vs OSS)
- auth mechanism and MCP transport
- non-secret Grafana/datasource identifiers
- enabled MCP tools/categories
- effective RBAC scopes
- actual MCP tool names observed
- actual query payload/result shape
- number of tool calls
- diagnosis latency
- Gate A pass/fail evidence

Only after Gate A passes should the repo advance to Loki/deeplinks/negative-case evidence and then approval/remediation/verification.
