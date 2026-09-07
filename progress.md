# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable deterministic safety core currently covers:

`strict telemetry mapping → eight-read metric preflight → metric activation pin → one bounded Loki preflight → Loki contract/datasource activation pin → official Grafana MCP Prometheus + Loki adapters → six-read metric diagnosis → mandatory production Loki corroboration → bounded Gemini advisory projection → audited IncidentService → trusted operator identity → revision-bound approval → governed allowlisted remediation → explicit credential-isolated HTTPS transport → two-read telemetry recovery verification`

Core invariants:

- Grafana remains the operational evidence plane; infrastructure write credentials remain separate.
- Production Prometheus and Loki datasource identities and semantic contracts are pinned by expiring activation artifacts.
- Production investigation uses six metric reads first and one bounded Loki corroboration query only after metrics independently diagnose.
- Missing, truncated, or scope-inconsistent Loki evidence forces abstention.
- Gemini is advisory only. It receives no raw PromQL, raw LogQL, raw log bodies, endpoints, credentials, remediation clients, or free-form report summary/hypothesis text.
- Gemini cannot alter deterministic status, grant approval, initiate remediation, or declare recovery.
- Approval is tied to the exact evidence revision, single-use, and invalidated by fresh investigation.
- Production writes require explicit startup opt-in plus separate process-owned endpoint/credential configuration.
- Action acceptance is never recovery; Grafana telemetry must prove consecutive healthy samples.

## Completed milestones

- Deterministic broadcast telemetry simulator + Prometheus + provisioned Grafana local stack.
- Opt-in pinned official `grafana/mcp-grafana:1.1.0` path with write tools disabled.
- Deterministic four-class incident investigation with exactly six metric reads.
- MCP Prometheus adapter with fail-closed parsing and query provenance.
- Approval-gated remediation with distinct write boundary and telemetry-only recovery proof.
- Audited lifecycle service and narrow authenticated HTTP API.
- Strict configurable production telemetry mapping and eight-slot readiness preflight.
- SHA-256 pinned expiring metric activation for non-demo profiles.
- Governed production remediation policy with deterministic operation identity and bounded retry/timeout semantics.
- Credential-isolated HTTPS remediation transport and loopback idempotency receiver.
- Bounded semantic Loki corroboration using official Grafana MCP `query_loki_logs`.
- Separate Loki activation record pinning semantic log contract and actual Loki datasource identity.
- Canonical production bootstrap requiring both metric and Loki activation.
- First bounded Gemini incident-commander layer with strict structured context/output validation and a credential-free model fixture.

## Prior handoff — dual evidence activation

The previous run made metric+Loki correlation canonical in non-demo production bootstrap. It added `runtime/log_activation.py`, extended `runtime/preflight.py` to preflight/pin both evidence planes, injected the verified Loki client into `IncidentService`, and added bootstrap/log-activation tests. Production now requires `--activation` and `--log-activation`; datasource identities are derived from the actual MCP client instances. The prior run could not execute the Python suite because the local execution container could not resolve `github.com`.

## Run log — 2026-09-07 — bounded Gemini incident commander

### Inspected at start

Read this `progress.md` completely before selecting work. Then inspected the current `main` repository and specifically:

- `runtime/investigator.py`
- `runtime/incident_service.py`
- `runtime/log_evidence.py`
- `runtime/api.py`
- `runtime/bootstrap.py`
- `runtime/tests/test_incident_service.py`
- root `README.md`

The highest-value unblocked gap was the previous handoff: add Gemini above the deterministic metric+Loki safety core without letting the model acquire incident authority or infrastructure-write capability.

### Research / attributions checked

Reviewed current official Google documentation before choosing the adapter shape:

- Google Gen AI SDK supports structured JSON generation with `response_mime_type="application/json"` and a response schema.
- Current Vertex AI / Google Gen AI SDK examples use `google.genai.Client` and Application Default Credentials for Google Cloud usage.
- This project therefore keeps `google-genai` optional and lazily imported so missing Gemini credentials/dependencies never block the deterministic safety core.

Official references are recorded in `README.md`.

### Exact changes made

Added `runtime/gemini_commander.py`:

- defines a narrow `CommanderModel` protocol: bounded structured context in, JSON object out;
- adds immutable `IncidentBriefing` output;
- adds `build_commander_context()` which projects an already-computed deterministic `IncidentReport` into a deliberately small advisory context;
- limits metric evidence to six semantic slots and passes only class, numeric value, and support boolean;
- passes only Loki corroboration status, not raw LogQL, raw log lines, parsed log content, timestamps, or corroboration reason text;
- omits the free-form deterministic report summary and hypothesis text to reduce prompt-injection surface;
- validates production/feed/evidence identifiers against a strict bounded identifier grammar before they can enter the model prompt;
- includes an explicit authority map stating the model may not diagnose, approve, remediate, or declare recovery;
- derives a deterministic next step entirely from core status: `diagnosed → seek_human_approval`, `abstain → collect_more_evidence`, `no_incident → observe`;
- adds exact-schema output validation: no extra fields, bounded text/list lengths, and no model override of the deterministic next step;
- adds `GeminiCommander`, which exposes only `brief(report)` and has no reference to `IncidentService` or any remediation adapter;
- adds optional `GoogleGenAICommanderModel` using structured JSON output, temperature 0, 512-token cap, system instruction treating all JSON fields as data, and lazy `google-genai` imports;
- adds a Vertex AI environment constructor using `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, Application Default Credentials, and optional `STAGEGUARD_GEMINI_MODEL`.

Added `runtime/tests/test_gemini_commander.py`:

- proves raw PromQL does not cross the model boundary;
- proves raw LogQL and malicious raw log/reason text do not cross the model boundary;
- proves free-form hypothesis text does not cross the model boundary;
- proves explicit no-diagnose/no-approve/no-remediate/no-recovery authority flags are present;
- proves diagnosed incidents can only return `seek_human_approval`;
- proves Gemini cannot promote an abstention to approval;
- proves no-incident output cannot request evidence collection/action instead of `observe`;
- proves extra output fields such as a remediation command fail closed;
- proves oversized model prose fails closed;
- proves unsafe identifiers are rejected before the model is called.

Updated root `README.md`:

- added the Gemini advisory boundary to the executable architecture and safety table;
- documented exactly which data does and does not cross the model boundary;
- documented deterministic next-step mapping;
- documented optional Vertex AI / `google-genai` configuration;
- added current official Google Gen AI / Vertex AI references;
- revised the roadmap so the next increment is authenticated runtime/API wiring for the advisory briefing.

### Commits produced this run

- `3e7e11ed` — add bounded Gemini incident commander briefing layer
- `5e1cb54e` — test Gemini commander safety boundary
- `3338a07e` — document bounded Gemini commander layer

### Tests / checks / results

Attempted a clean checkout and targeted deterministic test run with:

```bash
git clone https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard
cd /tmp/stageguard
PYTHONPATH=runtime python -m unittest runtime.tests.test_gemini_commander -v
```

The execution container still fails DNS resolution for `github.com`, so checkout failed before Python could start. The new tests are therefore **not claimed as passing** in this environment.

No GitHub Actions workflow was created, triggered, or rerun as a workaround. No Grafana, Loki, Gemini, Google Cloud, operator, or remediation credential was used.

### Decisions made

1. **Gemini is not a tool-calling remediation agent.** Its first production role is explanation/operator communication only.
2. **Do not prompt with raw evidence text when semantic evidence is enough.** Raw queries/log text create needless injection and data-leakage surface.
3. **Deterministic next-step policy is outside the model.** The model must copy the policy result and validation rejects any divergence.
4. **Structured output is necessary but not sufficient.** StageGuard performs its own exact-key, length, identifier, and policy validation after model generation.
5. **Gemini remains optional.** Importing/running the deterministic safety core does not require `google-genai` or Google Cloud credentials.
6. **No write capability was expanded.** The new commander object has no service/remediation reference and cannot consume an approval or declare recovery.

### Current blockers / unknowns

- The deterministic Python suite remains unexecuted here because the execution container cannot resolve GitHub for a local checkout.
- The optional Google Gen AI SDK adapter has not yet been exercised against a live Vertex AI project/ADC session.
- Full Docker → Grafana → official MCP metric/Loki acceptance remains unverified on a Docker-capable host.
- OIDC/IAP, durable tamper-resistant audit storage, operator UI, and Google Cloud deployment remain implementation gates.

## Single best next step

**Wire `GeminiCommander` into the authenticated StageGuard runtime/API as an optional read/advisory endpoint bound to the current incident revision: return a briefing only for the current snapshot, audit only non-sensitive briefing provenance, ensure briefing generation never mutates incident/approval/outcome state, add API/service tests for stale revision and model failure behavior, and keep production startup functional when Gemini is disabled or credentials are absent.**
