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

## Run log — 2026-09-10 — readiness local-trust short circuit

### Inspected at start

Read `progress.md` completely before choosing work, then inspected the current repository tree and the production readiness path, especially:

- `runtime/readiness.py`
- `runtime/tests/test_readiness.py`
- the retained Google Cloud/Gemini acceptance work from the previous run

The live Google Cloud acceptance step remains blocked because this runtime has no authorized disposable GCP environment, so this run worked on the highest-value unblocked production-safety issue instead.

### Exact changes made

Updated `runtime/readiness.py` so local activation/pin trust is now a hard prerequisite for any external Grafana MCP readiness probe:

- metric and Loki activation records are still validated on every readiness request;
- if either activation is missing or invalid, readiness immediately fails closed;
- Prometheus/Loki MCP status is reported as `blocked` (or `missing` for an absent Loki client) rather than opening a new external connection;
- no MCP process/connect call or Grafana `get_datasource` request is attempted when local trust cannot make the process traffic-eligible;
- cached external success can no longer visually mask a newly failed activation state;
- external probe attempt counters remain unchanged for locally blocked checks;
- existing bounded TTL, stale-grace, failure-backoff, provider-error suppression, and single-flight behavior remain unchanged when local trust is valid.

Added `runtime/tests/test_readiness_local_short_circuit.py` covering:

- invalid metric activation blocks both external evidence-plane probes;
- invalid Loki activation blocks both external probes;
- missing Loki dependency does not cause a Prometheus-only probe that cannot make readiness succeed;
- valid local trust still probes both Grafana evidence planes;
- blocked checks do not increment external-probe attempt metrics.

Updated `runtime/tests/test_readiness.py` to align the existing cached-success regression test with the stricter contract and to assert that failed/missing local trust returns `blocked` without additional MCP connects.

Commits created this run:

- `41cbdce8798e39c6b69f32153cca3f7c6b6d1faa` — short-circuit MCP readiness when local trust fails
- `d4823f8e1b9c1a1f52832835e5d5d1060dcf2843` — readiness local-trust short-circuit tests
- `30e858a2ce6ce42265a21285e17bd398b31d934b` — align existing readiness regression contract

### Tests / checks / results

Attempted a clean executable verification with:

`PYTHONPATH=runtime python -m unittest runtime.tests.test_readiness runtime.tests.test_readiness_local_short_circuit -v`

A fresh checkout could not be created because the execution container still cannot resolve `github.com`, so the committed test modules could not be executed locally. No PASS claim is made for these new changes.

Source-level verification through the GitHub connector confirmed the committed readiness logic and the aligned test expectations.

No GitHub Actions workflow was created, triggered, or rerun. No Grafana instance, MCP server, Google Cloud resource, IAM policy, secret, Gemini endpoint, or remediation endpoint was modified.

### Decisions made

1. **Local trust precedes network readiness.** If activation/pin validation cannot pass, external Grafana access cannot make the process safe to receive traffic.
2. **Blocked is distinct from failed.** `blocked` means the external check was intentionally not attempted because a prerequisite failed; `failed` remains reserved for attempted external checks that did not succeed.
3. **Do not spend external capacity on impossible readiness.** This reduces unnecessary MCP process churn and Grafana API load during expired, missing, or drifted activation states.
4. **Preserve fail-closed semantics over cached optics.** A previously healthy Grafana probe is not surfaced as current `ok` once local trust has failed.

### Current blockers / unknowns

- The new readiness tests still need empirical execution from a checkout with working GitHub/DNS access.
- `runtime.tests.test_gemini_acceptance_smoke` still needs empirical execution.
- `ENABLE_GEMINI=true python scripts/gcp_deploy_doctor.py --json` still needs a live authorized disposable GCP project.
- `python scripts/gemini_acceptance_smoke.py --execute --json` still needs one real authorized Vertex AI acceptance run after the doctor passes.
- Historical full-suite failures/errors still need systematic triage.

## Single best next step

**When an executable checkout is available, run the focused readiness tests first, then run the full unittest suite and classify every remaining failure/error into product defect vs optional/environmental integration. Fix the highest-severity real product defect before adding more deployment features.**

## Retained production hardening

### Google Cloud deployment doctor

`scripts/gcp_deploy_doctor.py` validates required deployment configuration, active `gcloud` identity, project consistency, required APIs, runtime service-account existence, Secret Manager resources without payload reads, effective secret access, effective Cloud Logging read/write permissions, conditional effective Vertex prediction permission, and Artifact Registry image availability. Offline validation can never report `ready_to_deploy=true`.

### Gemini acceptance smoke

`scripts/gemini_acceptance_smoke.py` defaults to configuration-only validation. A live Vertex request requires explicit `--execute`, uses only synthetic connectivity data, performs one bounded request, validates a locked response schema, reports `state_mutation=false`, and does not pass Grafana evidence, approval, remediation, or recovery state to the model.

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
