# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the indispensable runtime evidence plane. The proven vertical slice remains intact: deterministic telemetry, Prometheus/Loki/Grafana, official read-only Grafana MCP access, bounded diagnosis, optional revision-bound Gemini briefing, exact human approval, safe remediation, Grafana-based recovery verification, authenticated lifecycle state, and a same-origin operator cockpit.

Core invariants remain unchanged:
- Grafana is the evidence plane; infrastructure write credentials stay isolated from Grafana/MCP access.
- Gemini is optional/advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Human approval is single-use and bound to the exact evidence revision.
- Remediation success is never inferred from an action response; fresh Grafana telemetry must prove recovery.
- Local credentials/state remain under gitignored `.stageguard/` and `runtime/.secrets/` paths.
- Authenticated checkpointing, audit integrity, execution reconciliation, and no-replay protections remain implemented.

## Run log — 2026-09-10 — strict Cloud Run Gemini feature-flag parsing

### Inspected at start

Read `progress.md` completely before choosing work, then inspected the current repository tree, recent commits, `runtime/cloudrun_entrypoint.py`, `runtime/tests/test_cloudrun_entrypoint.py`, and `scripts/deploy_cloud_run.sh`.

The deploy helper already normalizes `ENABLE_GEMINI` strictly before forwarding it to Cloud Run, but the production runtime entrypoint independently treated every unrecognized `STAGEGUARD_ENABLE_GEMINI` value as false. A manual deployment, altered revision, or configuration drift could therefore silently disable Gemini on a typo such as `treu` instead of refusing startup.

### Exact changes made

Updated `runtime/cloudrun_entrypoint.py`:
- added an explicit false-value set (`0`, `false`, `no`, `off`);
- added `_optional_bool()` for bounded production feature-flag parsing;
- missing/blank values retain the safe default `False`;
- documented true/false aliases are accepted case-insensitively with surrounding whitespace;
- every other non-empty value now raises `ValueError` and causes Cloud Run startup to fail closed;
- `STAGEGUARD_ENABLE_GEMINI` now goes through this parser before `--enable-gemini` is added.

Updated `runtime/tests/test_cloudrun_entrypoint.py`:
- added true-alias coverage;
- added false-alias and blank-value coverage;
- added regression cases proving malformed values (`treu`, `enabled`, `2`, `maybe`) fail closed and identify `STAGEGUARD_ENABLE_GEMINI` in the bounded error.

Commits created this run:
- `9bd141463d66dd1e51033b21dad219065e750ce9` — fail closed on invalid Cloud Run Gemini flag
- `2bf04c85b588aabd833472bdfdb01b2fbad085cc` — test strict Cloud Run Gemini flag parsing

### Tests / checks / results

Source-level verification through the GitHub connector confirmed the committed runtime uses `_optional_bool()` and the regression test file contains explicit accepted/rejected value sets.

This automation runtime still does not provide an executable checkout of the repository, so the Python unittest module could not be empirically executed here. No green-suite claim is made for this change.

No GitHub Actions workflow was created, triggered, or rerun. No Grafana instance, MCP server, Google Cloud resource, IAM policy, secret, Gemini endpoint, or remediation endpoint was modified.

### Decisions made

1. **Production configuration typos must fail closed.** Silently changing model availability is operationally ambiguous and can hide deployment drift.
2. **The runtime validates independently of deployment tooling.** `deploy_cloud_run.sh` being strict is not sufficient because StageGuard can be deployed by other mechanisms.
3. **Blank means the documented safe default; malformed non-blank does not.** This preserves opt-in Gemini behavior without accepting accidental values.

### Current blockers / unknowns

- `runtime.tests.test_cloudrun_entrypoint`, `runtime.tests.test_command_line`, focused MCP/readiness tests, and the full unittest suite still need empirical execution from a runnable checkout.
- `runtime.tests.test_gemini_acceptance_smoke` still needs empirical execution.
- `ENABLE_GEMINI=true python scripts/gcp_deploy_doctor.py --json` still needs a live authorized disposable GCP project.
- `python scripts/gemini_acceptance_smoke.py --execute --json` still needs one real authorized Vertex AI acceptance run after the doctor passes.
- Historical full-suite failures/errors still need systematic triage.

## Single best next step

**Harden the remaining Cloud Run production configuration boundary by validating checkpoint object/bucket configuration and HMAC-secret representation against the actual bootstrap contract, then add focused regression coverage; when a runnable checkout is available, execute the Cloud Run, command-line, MCP/readiness, and full unittest suites before adding broader deployment features.**

## Retained production hardening

- Runtime MCP launcher parsing is now centralized and cross-platform, preserving Windows paths while failing closed on malformed quoting.
- Readiness validates local activation/pin trust before spawning or querying Grafana MCP clients.
- `scripts/gcp_deploy_doctor.py` validates deployment configuration, required APIs, runtime service account, Secret Manager resources/access, Cloud Logging permissions, conditional Vertex prediction permission, and image availability; offline validation cannot report deploy-ready.
- `scripts/gemini_acceptance_smoke.py` defaults to validation-only and requires explicit `--execute` for one bounded synthetic Vertex request.
- `scripts/deploy_cloud_run.sh` forwards the explicit Google Cloud project, location, Gemini model, IAP identity configuration, Secret Manager mounts, and keeps production remediation disabled.
- Operator/API safety continues to expose bounded incident/evidence/reconciliation state without raw queries or credentials.

## Validation baseline retained

- Local onboarding doctor: 8 tests passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from the last executable run: 81/81 passed.
- Historical full suite baseline: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Live Docker rehearsal: PASS twice consecutively.
- Official Grafana MCP read-only smoke path: PASS using `grafana/mcp-grafana:1.3.0`.
- Incident flow: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.
- Gemini integration is implemented; live production authorization/inference acceptance remains pending an authorized disposable GCP environment.
