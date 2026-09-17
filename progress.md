# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The implemented vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded investigation and diagnosis, optional Gemini briefing, exact-revision approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated private metrics bridging, evidence-unavailable abstention, no-replay execution reconciliation, recovery-only Grafana rechecks, stdio-only Grafana MCP launchers, strict operator-API authentication/framing/protocol preflight, and a loopback reference remediation provider with idempotent writes plus read-only operation reconciliation.

## Core invariants

- Grafana/MCP is read-only evidence access; infrastructure-write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Required evidence unavailability prevents briefing, approval, and execution from becoming actionable.
- Approval is exact-revision-bound and single-use; provider acceptance never counts as recovery.
- Fresh Grafana telemetry is required to verify recovery; `recovery_unverified` cannot replay remediation.
- Ambiguous remediation execution remains behind the execution-uncertainty barrier until durable reconciliation and fresh evidence resolve it.
- Operator API and reference remediation provider reject ambiguous credential/body framing before mutation.
- Consolidated validation resolves only direct non-symlink files under `runtime/tests`, fails closed on empty gates, is non-interactive and timeout-bounded, scrubs Grafana/Gemini/Google credentials (including inline Google service-account JSON forms), inherited proxy URLs/credentials, and Python injection controls, disables user-site packages/bytecode writes, isolates well-known Google ADC/gcloud home locations, blocks ambient GCE metadata-server credential discovery during execution, tests its own harness first, validates runtime activation before operator/API gates, executes overlapping gate selections only once under their earliest owner, and classifies subprocess launch failures as validation failures.

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected Windows-specific permission test skipped.
- Focused core/API/UI suite from the last executable repository run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; there is no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, predating latest hardening/recovery work.
- Historical official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0`; pinned `1.4.1` still requires a live smoke.
- Current connector-authored tests have not been repository-executed in this runner and are not treated as passing tests.

## Latest run — 2026-09-17 — validation proxy credential isolation

### Inspected at start

Read `progress.md` completely first, then inspected the runtime tree, consolidated validator, validator self-tests, and outstanding validation blockers. The validator already scrubbed StageGuard/Grafana/Gemini/Google credentials, isolated local ADC/gcloud homes, and blocked ambient GCE metadata identity. One host-environment leak remained: standard HTTP(S)/ALL proxy variables were inherited unchanged. Proxy URLs commonly support embedded `user:password@host` credentials and can reroute requests made by tests, so they do not belong in dependency-light safety subprocesses.

### Changes / actions

- Added `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, and `NO_PROXY` to exact-name sensitive environment handling; matching remains case-insensitive, covering lowercase variants commonly used on Unix.
- Added a deterministic `NO_PROXY=localhost,127.0.0.1,::1` override after sanitization so local test traffic stays direct while inherited bypass policy cannot reintroduce production/internal hostnames.
- Added regression coverage with credential-bearing proxy URLs proving proxy values and embedded credentials do not reach validation subprocess environments.
- Extended case-insensitive sensitive-name coverage for all proxy controls.
- Updated validator documentation to state that explicit live/integration smoke commands, rather than dependency-light regression tests, own network/proxy configuration.
- No credentials were read or supplied. No Docker, cloud resources, remediation targets, GitHub Actions, or unrelated repositories were touched.

### Checks / results

- Validator hardening committed as `024c2a3571e4d3c7f532b72535c52c676c44b4d4`.
- Regression coverage committed as `f4a6caff761ab2b751497f70552181d957610af8`.
- Static inspection confirms proxy variables are removed case-insensitively before the safe local-only `NO_PROXY` override is applied.
- This connector environment does not expose an executable checkout, so the updated harness has not been repository-executed and no new green-test claim is made.
- GitHub Actions was intentionally not triggered as a substitute for local validation.

### Decisions

1. Treat inherited proxy URLs as credential-bearing host configuration even when they happen not to contain a password in a particular environment.
2. Do not preserve inherited `NO_PROXY`: it can contain production/internal hostnames and changes request routing semantics.
3. Preserve a deterministic loopback-only `NO_PROXY` because StageGuard's dependency-light tests legitimately use local HTTP surfaces and should never need a corporate/developer proxy for them.

### Blockers / unknowns

- The consolidated runner still requires execution in a real checkout.
- Historical full-suite failures/errors still need classification from an executable checkout.
- A live read-only smoke against pinned `grafana/mcp-grafana:1.4.1` remains required.
- Disposable private Cloud Run acceptance still requires suitable credentials/environment and Docker.

## Single best next step

In an executable checkout, run `python scripts/run_stageguard_validation.py --list` and then `python scripts/run_stageguard_validation.py --keep-going`. Fix any failures before performing the pinned Grafana MCP 1.4.1 read-only live smoke.
