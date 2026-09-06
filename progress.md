# StageGuard Progress

## Current status

StageGuard has moved from an empty repository to an implementation-ready product/architecture specification for the Grafana track of Google Cloud Agentic Cinema.

**Current implementation gate:** prove the smallest real runtime slice using hackathon-permitted tooling:

`Gemini/ADK → official Grafana MCP → seeded live-production telemetry → evidence-grounded diagnosis`

Do not build broad UI or multiple scenarios before this works.

---

## Run log — 2026-09-06

### Inspected at start

- Repository `UnknownGod2011/grafana` was empty.
- No `progress.md`, README, architecture, source code, CI or other files existed.
- Therefore this run initialized the specification rather than attempting to extend nonexistent work.

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

#### `README.md`

Established:

- StageGuard product thesis
- target users
- live-production problem
- observe → investigate → correlate → act → verify workflow
- primary judge scenario
- why Grafana is indispensable
- autonomy/safety tiers
- real-user onboarding model
- MVP vertical slice
- evaluation metrics
- intended repository structure for the permitted implementation phase
- current official research links

#### `ARCHITECTURE.md`

Established:

- logical deployment topology
- production telemetry contract
- Grafana evidence layer
- Gemini/ADK responsibilities
- evidence ledger design
- operator incident cockpit
- bounded remediation adapter
- incident state machine
- deterministic investigation policy
- least-privilege/RBAC model
- prompt-injection and sensitive-telemetry boundary
- Google + Grafana agent-observability design
- deployment/onboarding strategy
- primary, secondary and negative test scenarios
- evaluation harness
- P0/P1/P2/P3 implementation order
- explicit MVP non-goals

#### `DEMO.md`

Established the exact three-minute judge narrative:

1. healthy three-camera broadcast
2. deterministic uplink-B packet-loss fault
3. Grafana alert / frame-drop symptom
4. agent investigates through Grafana MCP
5. evidence shows network fault rather than encoder overload
6. human approves reroute of Camera 3
7. safe remediation adapter executes
8. StageGuard re-queries Grafana
9. recovery is verified from telemetry
10. Grafana agent/MCP observability closes the sponsor story

### Decisions locked

1. **Primary use case:** live production/broadcast incident response, not generic application SRE.
2. **Primary demo failure:** Camera 3 frame drops caused by uplink-B packet loss.
3. **Sponsor dependency:** Grafana is the operational evidence source before and after remediation.
4. **Safety architecture:** Grafana investigation and remediation are separated; StageGuard does not get arbitrary shell/cloud access.
5. **Human-in-the-loop:** rerouting a live feed is a human-approved action in the demo.
6. **Resolution definition:** an incident is resolved only after Grafana telemetry verifies recovery.
7. **UX:** incident cockpit, not chatbot-first UI.
8. **Adoption path:** investigation-only mode → recommendations → human-approved actions → selective autonomy.
9. **Scope discipline:** one excellent vertical slice before additional failure types or broad integration work.

### Current blockers / unknowns

1. **No submitted implementation exists yet.** This is intentional because OpenAI tooling must not generate hackathon implementation artifacts under the stated rules; use Gemini CLI/Gemini Code Assist / permitted Google tooling for implementation.
2. **Grafana environment is not provisioned/connected yet.** Need to decide between hosted Grafana Cloud MCP and official OSS `mcp-grafana` based on the fastest reliable permitted implementation path.
3. **Google Cloud project/runtime is not connected yet.** Need permitted Gemini/ADK runtime setup.
4. **No deterministic telemetry simulator exists yet.** The first simulator should implement only the three-camera/two-uplink scenario.
5. **No Grafana dashboards/alerts/data sources exist yet.** They must be created during the permitted coding/setup phase.
6. **No remediation adapter exists yet.** It should initially manipulate only synthetic routing state.
7. **No LICENSE file exists.** The official rules require the public repo to include a detectable open-source license before submission.
8. **Hosted project URL and demo assets do not exist yet.**
9. **Need to confirm exact Grafana MCP tool names available in the chosen environment/version when implementation begins rather than hard-code assumptions from docs.

### Risks to watch

- Sponsor integration becomes cosmetic instead of being visible in the actual runtime path.
- Too much effort goes into dashboard polish before MCP connectivity works.
- Agent performs a plausible-looking diagnosis without enough retrieved evidence.
- Demo remediation is declared successful without telemetry verification.
- Permissions are broader than necessary, weakening the production-ready story.
- Optional Grafana AI Observability distracts from required core MCP use.
- Demo relies on nondeterministic external failures and becomes unreliable during judging.
- More scenarios/features are added before the core one can be reset and replayed reliably.

---

## Single best next step

**Using hackathon-permitted Google tooling, implement and document one minimal integration spike that proves a Gemini/ADK agent can call the official Grafana MCP server against a seeded Grafana instance, retrieve the Camera 3 frame-drop + uplink-B packet-loss evidence, and return a structured diagnosis with Grafana evidence references.**

Acceptance criteria for that spike:

- real Gemini/Google agent invocation
- real official Grafana MCP invocation
- at least two real Grafana telemetry lookups
- diagnosis correctly identifies uplink B
- evidence clearly distinguishes network failure from encoder overload
- no remediation yet
- repeatable from a clean demo state

Only after this passes should the next run specify/implement the approval + remediation + verification loop.

---

## Sources to re-check during implementation

- https://agentic-cinema.devpost.com/rules
- https://grafana.com/docs/grafana/latest/developer-resources/mcp/introduction/
- https://grafana.com/docs/grafana/latest/developer-resources/mcp/reference/mcp-tools-table/
- https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/cloud-mcp/
- https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/oss-mcp/configure/enable-and-disable-tools/
- https://grafana.com/docs/grafana-cloud/observe-and-act/monitor-applications/ai-observability/mcp-observability/
- https://github.com/grafana/mcp-grafana
- https://grafana.com/ai/
- https://docs.cloud.google.com/gemini-enterprise-agent-platform/build/runtime/quickstart-adk
