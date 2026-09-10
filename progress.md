# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the indispensable runtime evidence plane. The working vertical slice remains: deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, restart reconciliation, and a same-origin operator cockpit.

Core invariants:
- Grafana is the evidence plane; infrastructure write credentials stay isolated from Grafana/MCP access.
- Gemini is optional/advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact evidence revision.
- Remediation success is never inferred from an action response; fresh Grafana telemetry must prove recovery.
- Authenticated checkpoints and audit integrity fail closed.

## Run log — 2026-09-10 — executable fake-gcloud deployment boundary harness

### Inspected at start

Read `progress.md` completely before choosing work. Then inspected:
- `scripts/deploy_cloud_run.sh`
- `runtime/tests/test_cloud_run_deploy_contract.py`

The previous handoff explicitly identified a remaining validation gap: source-level assertions covered the checkpoint object byte/whitespace contract, but the shell helper itself had not been exercised end-to-end with a fake `gcloud` executable.

### Exact changes made

Added `runtime/tests/test_cloud_run_deploy_shell.py` as a credential-free execution harness for the production deploy helper.

The test:
- creates an isolated temporary `PATH` containing a fake `gcloud` shim;
- provides only synthetic project/service/Grafana/Secret Manager identifiers;
- captures every `gcloud` invocation to a temporary file instead of touching Google Cloud;
- executes the real `scripts/deploy_cloud_run.sh` under Bash;
- verifies a checkpoint object of exactly 512 ASCII/UTF-8 bytes reaches the fake deploy and IAM-binding commands;
- verifies 513 ASCII bytes fail with exit code 2 before any `gcloud` invocation;
- verifies a 300-character multibyte value (`é` repeated 300 times, 600 UTF-8 bytes) fails before `gcloud`, proving the shell uses bytes rather than character count;
- verifies leading and trailing whitespace fail before `gcloud`;
- verifies valid input causes exactly the expected two `gcloud` command families: `run deploy` and `run services add-iam-policy-binding`.

Commit created:
- `60538f0820dcf575886b76c36a951be06db9059c` — test Cloud Run deploy helper with fake gcloud

### Tests / checks / results

Attempted to execute the newly committed test from a fresh checkout:

```text
git clone --depth 1 https://github.com/UnknownGod2011/grafana.git /tmp/stageguard
python -m unittest runtime.tests.test_cloud_run_deploy_shell
```

The execution container failed at clone time because DNS could not resolve `github.com`. Therefore the new shell suite was not empirically executed in this runtime and no green-suite claim is made.

The committed test file was re-read through the GitHub connector after creation to verify the repository contains the intended fake-`gcloud` harness.

No GitHub Actions workflow was created, triggered, or rerun. No Grafana instance, MCP server, Google Cloud project, bucket, object, IAM policy, Secret Manager payload, Gemini endpoint, or remediation endpoint was modified.

### Decisions made

1. Deployment safety boundaries should have behavioral shell tests, not only source-string contract assertions.
2. Fake command shims are preferred for deployment helper tests because they validate argument flow and fail-before-external-call behavior without cloud credentials or billable operations.
3. The 512-byte checkpoint object rule remains aligned across deploy helper, deployment doctor, and runtime.
4. Missing cloud credentials or transient checkout DNS do not block useful credential-free implementation work.

### Current blockers / unknowns

- The new `runtime.tests.test_cloud_run_deploy_shell` suite still needs empirical execution from a runnable checkout.
- The focused deployment/entrypoint/doctor suites still need empirical execution from a runnable checkout.
- The exact Cloud Storage object Policy Troubleshooter tuple still needs one authorized disposable-project acceptance run.
- `ENABLE_GEMINI=true python scripts/gcp_deploy_doctor.py --json` still needs a live authorized disposable GCP project.
- `python scripts/gemini_acceptance_smoke.py --execute --json` still needs one real Vertex AI acceptance run after the doctor passes.
- Historical full-suite failures/errors still need systematic triage after the repository can be executed locally.

## Single best next step

**When repository execution is available, run `runtime.tests.test_cloud_run_deploy_shell` together with `runtime.tests.test_cloud_run_deploy_contract`, `runtime.tests.test_cloudrun_entrypoint`, and `runtime.tests.test_gcp_deploy_doctor`; fix any behavioral mismatch immediately. If those are green, broaden the fake-command harness to assert that secret payloads can never appear in the deploy helper's `--set-env-vars` arguments and that invalid Gemini/location/model values also fail before `gcloud`.**

## Previous run — checkpoint deploy/runtime validation parity

The previous run fixed a real deploy/runtime mismatch for `CHECKPOINT_OBJECT`: Bash character-count validation was replaced by a 512 UTF-8-byte bound and leading/trailing whitespace now fails before deployment. Source-level regression coverage verifies parity with `gcp_deploy_doctor.py` and `cloudrun_entrypoint.py`.

Previous commits:
- `49b379f6875b103c2ac9b6ff913ee21ad6fe05ae` — align checkpoint object validation with runtime
- `f3330555ae4a7bf724c95b0ccf92ac4eee9a7a1a` — cover checkpoint object deploy parity

## Retained production hardening

- Cloud Run production deployment uses authenticated GCS checkpoints rather than silent ephemeral/no-checkpoint state.
- Runtime checkpoint HMAC keys are Secret Manager supplied and at least 32 UTF-8 bytes.
- Checkpoint object validation is byte-accurate and aligned across deploy helper, doctor, and runtime.
- Runtime MCP launcher parsing is centralized and cross-platform.
- Readiness validates local activation/pin trust before spawning/querying Grafana MCP.
- Deployment doctor validates required APIs, secrets/access, Cloud Logging permissions, checkpoint storage permissions, conditional Vertex prediction permission, and image availability; offline validation can never report deploy-ready.
- Gemini acceptance smoke defaults to zero model calls and requires explicit `--execute`.
- Standard Cloud Run deployment keeps production remediation disabled.

## Validation baseline retained

- Local onboarding doctor: 8 tests passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable run: 81/81 passed.
- Historical full suite baseline: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Live Docker rehearsal: PASS twice consecutively.
- Official Grafana MCP read-only smoke path: PASS using `grafana/mcp-grafana:1.3.0`.
- Incident flow: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.
