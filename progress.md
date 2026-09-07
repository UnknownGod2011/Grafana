# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable deterministic safety core currently covers:

`strict telemetry mapping → eight-read metric preflight → metric activation pin → one bounded Loki preflight → Loki contract/datasource activation pin → official Grafana MCP Prometheus + Loki adapters → six-read metric diagnosis → mandatory production Loki corroboration → authenticated IncidentService → optional revision-bound Gemini advisory briefing → revision-bound approval → governed allowlisted remediation → explicit credential-isolated HTTPS transport → two-read telemetry recovery verification`

Core invariants:

- Grafana remains the operational evidence plane; infrastructure write credentials remain separate.
- Production Prometheus and Loki datasource identities and semantic contracts are pinned by expiring activation artifacts.
- Production investigation uses six metric reads first and one bounded Loki corroboration query only after metrics independently diagnose.
- Missing, truncated, or scope-inconsistent Loki evidence forces abstention.
- Gemini is advisory only. It receives no raw PromQL, raw LogQL, raw log bodies, endpoints, credentials, remediation clients, or free-form report summary/hypothesis text.
- Gemini briefing requests must match the exact current incident ID and evidence revision before the model is called.
- Briefing generation cannot mutate incident, approval, remediation, or recovery state.
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
- Bounded Gemini incident-commander layer with strict structured context/output validation and credential-free model fixtures.
- Revision-bound authenticated Gemini briefing endpoint with non-sensitive provenance auditing and explicit bootstrap opt-in.

## Prior handoff

The previous run added `runtime/gemini_commander.py`: a narrow structured-output advisory layer above deterministic metric+Loki diagnosis. The model had no service/remediation reference and could not override deterministic next-step policy, but it was not yet connected to the authenticated incident lifecycle or canonical bootstrap.

## Run log — 2026-09-07 — revision-bound Gemini advisory runtime

### Inspected at start

Read this `progress.md` completely before selecting work. Then inspected current `main`, specifically:

- `runtime/incident_service.py`
- `runtime/api.py`
- `runtime/gemini_commander.py`
- `runtime/bootstrap.py`
- `runtime/tests/test_incident_service.py`
- `runtime/tests/test_api.py`
- root `README.md`

The highest-value unblocked gap was the prior handoff: bind Gemini generation to the authenticated current incident revision without allowing the model to acquire state mutation or write authority.

### Exact changes made

Updated `runtime/incident_service.py`:

- added optional `GeminiCommander` injection;
- added `briefing(incident_id, revision, actor)` as the only service-level model entrypoint;
- validates exact current incident ID + revision before model invocation;
- executes revision validation and generation while holding the lifecycle lock, so a concurrent investigation cannot advance the evidence revision between validation and generation;
- never changes `_snapshot`, approval, outcome, remediation client, metrics, or log state during briefing generation;
- records successful provenance as only revision + deterministic next step + SHA-256 briefing digest;
- does not copy model prose into lifecycle audit metadata;
- records provider failures using only the exception class and revision, then raises a generic `Gemini briefing generation failed` error to avoid leaking provider/credential details.

Updated `runtime/api.py`:

- added authenticated `POST /v1/briefing`;
- request schema accepts only `incident_id` and `revision`;
- actor identity still comes exclusively from the configured identity provider;
- no prompt, query, action, target, endpoint, credential, datasource, or operator identity can be supplied through the body;
- stale revision errors fail before model invocation.

Updated `runtime/bootstrap.py`:

- Gemini remains disabled by default;
- added explicit `--enable-gemini` opt-in;
- optional runtime composition uses `GoogleGenAICommanderModel.from_vertex_ai_environment()` only when enabled;
- default startup therefore remains functional without `google-genai`, Vertex AI credentials, or ADC;
- explicit Gemini opt-in fails startup if the optional dependency/environment is unavailable rather than silently degrading;
- retained separate production-remediation opt-in and credentials.

Added `runtime/tests/test_briefing_runtime.py`:

- proves briefing is bound to the current revision and leaves the complete incident snapshot unchanged;
- proves briefing cannot create approval or invoke remediation;
- proves stale revision is rejected before the model fixture is called;
- proves model/provider failure is redacted and leaves state unchanged;
- proves disabled Gemini does not affect deterministic investigation runtime;
- exercises the authenticated HTTP briefing endpoint with identity-provider actor provenance;
- proves stale API briefing requests return a bounded invalid-request error.

Updated `README.md`:

- made revision-bound Gemini briefing part of the executable vertical slice;
- documented `--enable-gemini` and Vertex AI environment requirements;
- documented audit redaction/digest behavior;
- documented `POST /v1/briefing` and its exact request boundary;
- moved the roadmap forward to identity/audit durability, full MCP acceptance, and operator console work.

### Commits produced this run

- `9ceed983` — bind Gemini briefings to incident revisions
- `3290f770` — expose revision-bound advisory briefing endpoint
- `f0624de2` — wire optional Gemini commander into production bootstrap
- `bfcf1ee8` — test revision-bound advisory runtime
- `355d41a4` — document revision-bound Gemini advisory runtime

### Tests / checks / results

Attempted a clean checkout and targeted deterministic test run with:

```bash
git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git /tmp/stageguard
cd /tmp/stageguard
PYTHONPATH=runtime python -m unittest \
  runtime.tests.test_briefing_runtime \
  runtime.tests.test_gemini_commander \
  runtime.tests.test_api \
  runtime.tests.test_incident_service -v
```

The execution container still fails DNS resolution for `github.com`, so checkout failed before Python could start. The new tests are therefore **not claimed as passing** in this environment.

No GitHub Actions workflow was created, triggered, or rerun as a workaround. No Grafana, Loki, Gemini, Google Cloud, operator, or remediation credential was used.

### Decisions made

1. **Briefing generation is revision-bound, not merely report-bound.** The authenticated caller must identify the exact current incident snapshot.
2. **The lifecycle lock protects snapshot identity during model generation.** This favors correctness and stale-result prevention over concurrent advisory throughput; model calls remain optional.
3. **Model prose is not lifecycle audit data.** Audit stores only a digest and deterministic next-step provenance to reduce sensitive-data retention.
4. **Provider error details do not cross the API boundary.** Only a bounded error class is audited.
5. **Gemini startup is explicit opt-in.** Missing AI credentials/dependencies cannot break normal deterministic StageGuard startup.
6. **No write authority was expanded.** The briefing path cannot approve, execute remediation, or declare recovery.

### Current blockers / unknowns

- The deterministic Python suite remains unexecuted here because the execution container cannot resolve GitHub for a local checkout.
- The optional Google Gen AI SDK adapter has not yet been exercised against a live Vertex AI project/ADC session.
- Full Docker → Grafana → official MCP metric/Loki acceptance remains unverified on a Docker-capable host.
- The current static bearer deployment primitive is not yet production identity; OIDC/IAP remains an implementation gate.
- Local JSONL audit is append-only but not tamper-resistant or centralized.
- No operator console or packaged Google Cloud deployment exists yet.

## Single best next step

**Implement a production identity + durable audit deployment boundary for Google Cloud: add an OIDC/IAP-capable identity provider that derives the trusted operator subject from verified claims, add a durable append-only audit sink abstraction suitable for Cloud Logging/structured storage without leaking evidence bodies or secrets, and add deterministic tests proving spoofed headers/claims cannot become operator identity. Keep the static bearer provider as local/development fallback only.**
