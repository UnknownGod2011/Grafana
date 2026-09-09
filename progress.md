# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the indispensable runtime evidence plane. The proven vertical slice remains intact: deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, and a same-origin operator cockpit.

Current productization priorities are real Grafana onboarding, production Google Cloud deployment, empirical acceptance testing, maintainability, and operational safety.

Core invariants remain unchanged:

- Grafana is the evidence plane; infrastructure write credentials stay isolated from Grafana/MCP access.
- Gemini is optional/advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact evidence revision.
- Remediation success is never inferred from an action response; fresh Grafana telemetry must prove recovery.
- Local credentials/state remain under gitignored `.stageguard/` and `runtime/.secrets/` paths.
- Authenticated checkpointing, audit integrity, execution reconciliation, and no-replay protections remain implemented.

## Run log — 2026-09-10 — opt-in Vertex/Gemini acceptance smoke

### Inspected at start

Read `progress.md` completely before choosing work. Inspected the current production-deployment path, especially:

- `scripts/gcp_deploy_doctor.py`
- `runtime/tests/test_gcp_deploy_doctor.py`
- `runtime/gemini_commander.py`
- `README.md`
- the prior Secret Manager, Cloud Logging, and conditional Vertex `aiplatform.endpoints.predict` Policy Troubleshooter gates

The previous run's live GCP verification step is still blocked by the absence of an authorized disposable Google Cloud environment in this runtime, so this run completed the next useful unblocked engineering step instead of stopping.

### Official documentation checked

Current Google documentation was rechecked before implementing the smoke path:

- the Google Gen AI SDK exposes `client.models.generate_content(...)`;
- Vertex AI usage is configured with a Google Cloud project and location;
- `gemini-2.5-flash` remains a valid documented generation model in the SDK documentation/examples;
- Application Default Credentials are the expected local authentication path for Vertex AI client use.

References:

- https://googleapis.github.io/python-genai/
- https://docs.cloud.google.com/vertex-ai/generative-ai/docs/samples/googlegenaisdk-textgen-with-multi-img

### Exact changes made

Added `scripts/gemini_acceptance_smoke.py`:

- defaults to configuration-only validation and sends zero model requests;
- requires an explicit `--execute` flag before any live Gemini request is possible;
- resolves the same production environment contract used by StageGuard (`GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `STAGEGUARD_GEMINI_MODEL`);
- validates project/location/model identifiers before SDK initialization;
- performs exactly one bounded `generate_content` call when explicitly executed;
- sends only a synthetic connectivity prompt, with no incident, Grafana, PromQL, LogQL, secret, approval, remediation, or recovery data;
- requests a tiny locked JSON schema with `temperature=0` and `max_output_tokens=48`;
- validates the response exactly as `{status: ok, purpose: stageguard-gemini-acceptance}`;
- reports `state_mutation=false` and never changes StageGuard state or any Google Cloud resource;
- distinguishes pre-request failures from actual request attempts;
- suppresses arbitrary provider exception text so SDK/transport details are not copied into CI logs or deployment reports.

Added `runtime/tests/test_gemini_acceptance_smoke.py`:

- proves default mode is validation-only;
- covers missing/malformed project, location, and model identifiers;
- proves `_execute_smoke` is not called without `--execute`;
- proves the explicit execute path calls the executor once;
- covers safe pre-request and request-started failure accounting;
- locks the state-isolation/no-Grafana-secret contract.

Added `docs/gemini-acceptance.md`:

- documents the safe sequence: config validation -> live `gcp_deploy_doctor.py --json` -> one opt-in acceptance request;
- explicitly states that the smoke proves only Vertex/Gemini connectivity/authorization and does not prove diagnosis, approval, remediation, or recovery correctness.

Commits created this run:

- `fa11165de9021b7e6b1c47c313fe62267dfd3615` — initial opt-in Gemini acceptance smoke
- `f40f342b684239f0708f5c11909ee24210d756ad` — acceptance smoke regression tests
- `dccc6f0a892a6e2eb6087e6f1f8835486be55519` — acceptance documentation
- `44b57c1a34e0fa275cb8fb6d92aeb61f25ce4618` — safe failure reporting and request-attempt accounting
- `2a20e054617a419644978b68428ac67e0b371b89` — aligned safe-failure regression coverage

### Tests / checks / results

- Source-level inspection of the committed smoke command and tests completed through the GitHub connector.
- Attempted a fresh executable checkout with `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git`; the execution container still cannot resolve `github.com`, so the committed unittest module could not be executed locally.
- No PASS claim is made for the new tests.
- No GitHub Actions workflow was created, triggered, or rerun.
- No Google Cloud resource, IAM policy, API, secret, Grafana instance, Gemini endpoint, or remediation endpoint was modified.
- The live `--execute` smoke was intentionally not attempted because this runtime has no authorized disposable Google Cloud environment.

### Decisions made

1. **Live inference must be explicit.** Merely running the smoke command cannot incur a Gemini request.
2. **Keep acceptance state-isolated.** The smoke verifies SDK/auth/model connectivity with synthetic data rather than passing a real incident through Gemini.
3. **Bound cost and output.** One request, deterministic temperature, tiny schema, and a small output-token limit are sufficient for acceptance.
4. **Do not leak provider errors.** Arbitrary SDK exception strings are replaced with bounded operator-safe failure codes/messages.
5. **Do not confuse connectivity with correctness.** Passing the smoke cannot mark StageGuard production-ready by itself; deterministic policy and Grafana verification remain separate gates.

### Current blockers / unknowns

- The new `runtime.tests.test_gemini_acceptance_smoke` module still needs empirical execution from a checkout with working GitHub/DNS access.
- The existing live `gcp_deploy_doctor.py --json` Vertex Policy Troubleshooter check still needs confirmation in a disposable authorized Google Cloud project.
- The new `gemini_acceptance_smoke.py --execute --json` path still needs one real authorized Vertex AI run after the doctor passes.
- Historical broader-suite failures/errors still need systematic triage.

## Single best next step

**On a disposable authorized Google Cloud project, run `ENABLE_GEMINI=true python scripts/gcp_deploy_doctor.py --json`; if and only if the doctor reports ready, run `python scripts/gemini_acceptance_smoke.py --execute --json` once and record the exact non-secret result. If credentials are still unavailable, the next unblocked engineering task is to triage the historical full-suite failures into real product defects versus optional/environmental integration failures.**

## Retained production hardening

### Google Cloud deployment doctor

`scripts/gcp_deploy_doctor.py` validates required deployment configuration, active `gcloud` identity, project consistency, required APIs, runtime service-account existence, Secret Manager resources without payload reads, effective secret access, effective Cloud Logging read/write permissions, conditional effective Vertex prediction permission, and Artifact Registry image availability. Offline validation can never report `ready_to_deploy=true`.

### Cloud Run / Vertex runtime contract

`scripts/deploy_cloud_run.sh` forwards `GOOGLE_CLOUD_PROJECT`, optional `GOOGLE_CLOUD_LOCATION` (default `global`), and optional `STAGEGUARD_GEMINI_MODEL` (default `gemini-2.5-flash`). The standard Cloud Run artifact exposes no production-remediation switch or write credential.

### Operator and evidence safety

The cockpit surfaces incident state, root cause, confidence, evidence revision, human approval, Grafana MCP provenance, and the `ACTION ACCEPTED ≠ INCIDENT RESOLVED` recovery-verification sequence. Bounded lifecycle responses expose provenance and timing while excluding raw queries and secrets.

## Validation baseline retained

- Local onboarding doctor: 8 tests passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable run: 81/81 passed.
- Historical full suite baseline: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Live Docker rehearsal: PASS twice consecutively.
- Official Grafana MCP read-only smoke path: PASS using `grafana/mcp-grafana:1.3.0`.
- Incident flow: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.
- Gemini integration is implemented; live production authorization/inference acceptance remains pending an authorized disposable GCP environment.
