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

## Run log — 2026-09-10 — cross-platform MCP launcher parsing

### Inspected at start

Read `progress.md` completely before choosing work, then inspected the current repository tree, recent commits, `runtime/readiness.py`, both official Grafana MCP runtime adapters, and the existing MCP adapter tests.

The requested full-suite execution remains blocked in this execution container because a clean checkout still fails DNS resolution for `github.com`. Rather than add speculative deployment work, this run inspected the runtime source for a concrete unblocked defect and found the same Windows command-line parsing class previously fixed in the onboarding doctor still existed in the production MCP adapters.

### Exact changes made

Added `runtime/command_line.py` with one shared `split_command()` helper for child-process launcher configuration:

- POSIX launchers retain normal POSIX `shlex` parsing;
- Windows launchers use non-POSIX parsing so unescaped path backslashes such as `C:\\Python312\\python.exe` are preserved;
- one matching wrapper quote pair is removed from Windows tokens before argv is passed directly to subprocess launchers;
- empty commands and malformed quoting fail closed with bounded configuration errors;
- the platform choice is injectable for deterministic cross-platform tests.

Updated `runtime/mcp_metric_client.py` and `runtime/mcp_log_client.py` so `STAGEGUARD_MCP_COMMAND` is parsed through the shared helper instead of unconditional POSIX `shlex.split`.

Added `runtime/tests/test_command_line.py` covering:

- POSIX quoted arguments;
- unquoted absolute Windows executable paths with backslashes;
- quoted Windows executable paths containing spaces;
- quoted ordinary Windows arguments;
- empty launcher commands;
- unbalanced quotes.

Commits created this run:

- `9e0cf0ff37d46e077835eaeb2f1991d910b70144` — add cross-platform MCP command parser
- `ef4566c1171fd6cf20b2cfccb80bb7f1d6f66ad3` — wire metric MCP adapter to shared parser
- `1635ac9c564dc581c93b88ebd0d0204612fa744d` — wire Loki MCP adapter to shared parser
- `b3ae3dfaef1b68bf80d5f26d41e692c612f4c8f0` — add parser regression tests

### Tests / checks / results

Attempted a fresh checkout with `git clone --depth 1 https://github.com/UnknownGod2011/Grafana.git`; the execution container still returned `Could not resolve host: github.com`, so the committed unittest module could not be executed from the repository and no green-suite claim is made.

The critical parser behavior was independently exercised with Python's stdlib `shlex`: POSIX mode demonstrably transforms `C:\\Python312\\python.exe` into a path with stripped backslashes, while the new Windows-mode parsing preserves the backslashes and quoted argument grouping. Source-level verification through the GitHub connector confirmed both runtime adapters now call the shared parser.

No GitHub Actions workflow was created, triggered, or rerun. No Grafana instance, MCP server, Google Cloud resource, IAM policy, secret, Gemini endpoint, or remediation endpoint was modified.

### Decisions made

1. **Runtime and onboarding must use the same platform semantics.** Passing onboarding while the actual incident runtime corrupts the same launcher path is not acceptable.
2. **Pass argv directly; do not re-shell commands.** StageGuard keeps command configuration as an argument vector after parsing, avoiding another quoting/injection layer.
3. **Centralize launcher parsing.** Future MCP/evidence adapters should import one parser rather than independently choosing `shlex` behavior.
4. **Fail closed on malformed configuration.** Invalid quoting is reported as a bounded configuration error instead of being repaired heuristically.

### Current blockers / unknowns

- `runtime.tests.test_command_line`, the prior readiness tests, and the full unittest suite still need empirical execution from a checkout with working GitHub/DNS access.
- `runtime.tests.test_gemini_acceptance_smoke` still needs empirical execution.
- `ENABLE_GEMINI=true python scripts/gcp_deploy_doctor.py --json` still needs a live authorized disposable GCP project.
- `python scripts/gemini_acceptance_smoke.py --execute --json` still needs one real authorized Vertex AI acceptance run after the doctor passes.
- Historical full-suite failures/errors still need systematic triage.

## Single best next step

**When an executable checkout is available, run `runtime.tests.test_command_line` plus the focused MCP/readiness suites first, then run the complete unittest suite and fix the highest-severity genuine product failure before adding more deployment features.**

## Previous run — readiness local-trust short circuit

`runtime/readiness.py` now validates metric/Loki activation and semantic/datasource pins before attempting any external Grafana MCP readiness work. Invalid local trust fails closed, reports external probes as `blocked`/`missing`, does not spawn/connect MCP clients, cannot be masked by cached success, and does not increment external-attempt counters. Dedicated regression coverage was added in `runtime/tests/test_readiness_local_short_circuit.py`, with the existing readiness cache test aligned to the stricter contract.

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
