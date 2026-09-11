# StageGuard Progress

## Current status

StageGuard is a personal open-source Gemini/Google Cloud incident commander for live media workflows with Grafana as the read-only runtime evidence plane. The current vertical slice includes deterministic telemetry, Prometheus/Loki/Grafana, official Grafana MCP access, bounded diagnosis, optional Gemini briefing, revision-bound approval, remediation adapters, telemetry-verified recovery, authenticated lifecycle state, checkpoint/audit integrity, operator UI, Cloud Run deployment hardening, watchdog observability, authenticated metrics bridging, stale/scrape detection, pinned local acceptance images, strict Prometheus/MCP evidence parsing, structured evidence-unavailable abstention, and fail-closed operator handling for observability-plane outages.

Core invariants:
- Grafana/MCP is read-only evidence access; infrastructure write credentials remain isolated.
- Gemini is advisory and cannot mutate diagnosis, approval, remediation, or recovery state.
- Approval is exact-revision-bound and single-use.
- Provider action success never counts as recovery; fresh Grafana telemetry must prove it.
- Durable checkpoint/audit integrity failures fail closed.
- Loss of observability must never be reclassified as a positive remediation deadline breach.
- Ambiguous, malformed, nonnumeric, or non-finite evidence must never be interpreted as healthy evidence.
- Expected evidence-plane transport/protocol failures become sanitized abstention, not diagnosis.
- Programming/configuration defects remain visible exceptions.
- Partial, missing, or unavailable evidence must never reach infrastructure mutation.
- The browser must never turn evidence unavailability into an actionable diagnosis or expose provider failure detail.

## Run log — 2026-09-11 — real-browser evidence-unavailable acceptance

### Inspected at start

Read `progress.md` completely before deciding what to change. Inspected:
- `runtime/operator_console.py`
- `runtime/tests/test_operator_console.py`
- `runtime/tests/test_evidence_unavailable_lifecycle.py`
- repository/runtime layout relevant to test execution
- `OPERATOR_CONSOLE.md`

The previous run had completed the fail-closed DOM implementation and string-level regressions. The highest-value unblocked gap was executable browser proof using a real authenticated `/v1/incident` response.

### Exact changes made

#### Added real-browser safety acceptance

Created `runtime/tests/test_operator_browser_evidence_unavailable.py`.

The test:
- uses the real `IncidentService` rather than a copied JSON fixture;
- returns one symptom metric and then raises `EvidenceUnavailable` on the required causal read;
- embeds secret/provider endpoint sentinels in the thrown provider error;
- starts the real StageGuard HTTP server with `StaticBearerIdentityProvider`;
- launches headless Chromium through optional Playwright;
- authenticates all browser requests using the test bearer header;
- loads the shipped `/console` and `/assets/operator.js`;
- waits for the actual evidence-unavailable safety card to render;
- verifies Gemini briefing, revision entry, approval, and execution controls are disabled;
- verifies the root cause renders as `Not established`;
- verifies the remediation adapter receives zero calls;
- verifies provider secret/endpoint sentinels are absent from rendered body text and serialized page HTML;
- verifies the first-viewport proof layer also renders `EVIDENCE UNAVAILABLE` and `Not established`.

Playwright remains an optional test-only dependency; production/runtime code gains no browser automation dependency. If Playwright is absent, unittest skips this module rather than failing the core suite.

Commits:
- `15f5c86e24cb768928d7ccf821e90bcbe75d3fe3` — initial browser fail-closed acceptance
- `482e341f9833d6eae9b5d001b973b10fc32c0c01` — correct invocation guidance for the runtime import layout

#### Added contributor/release documentation

Created `docs/operator-browser-acceptance.md` describing:
- installation and Chromium setup;
- the exact command to run from `runtime/`;
- the complete browser-facing safety chain under test;
- release-blocking failure semantics;
- why Playwright is optional and not a StageGuard runtime dependency.

Commits:
- `a753d6fa4d54e6e64ea1a17b006f33f07a420ca9` — browser acceptance documentation
- `05975a8b456ae4c4a7d9ae25efc53ba2fb7e9f4b` — corrected run instructions

### Checks / results

Attempted a fresh executable checkout and focused test run:

```bash
git clone --depth 1 https://github.com/UnknownGod2011/grafana.git /tmp/stageguard
cd /tmp/stageguard
python -m unittest runtime.tests.test_operator_browser_evidence_unavailable runtime.tests.test_operator_console runtime.tests.test_evidence_unavailable_lifecycle
```

The execution container failed before checkout with:

```text
Could not resolve host: github.com
```

Therefore no claim is made that the Playwright acceptance, focused unittest set, or Docker rehearsal is green in this run. Repository reads/writes and post-write inspection succeeded through the connected GitHub integration.

No GitHub Actions workflow was created, triggered, rerun, or modified. No Grafana Cloud, GCP/IAM/Cloud Run, Gemini, checkpoint, audit, or remediation resource was changed.

### Decisions

1. Use a real browser against the real authenticated StageGuard server rather than adding another string-only frontend test.
2. Generate the abstained incident through `IncidentService` so the test covers `EvidenceUnavailable -> service -> API -> JavaScript -> DOM` end to end.
3. Inject explicit secret/provider sentinels into the underlying exception and assert they never appear in DOM text or serialized page HTML.
4. Keep Playwright optional so core/local/free development stays lightweight and production dependencies remain unchanged.
5. Treat disagreement between the authoritative cockpit and the first-viewport proof layer as a release-blocking regression.
6. Do not use GitHub Actions merely to compensate for the current container DNS failure.

### Blockers / unknowns

- The new Playwright acceptance still needs execution in an environment with a runnable checkout, Playwright, and Chromium.
- `runtime/tests/test_operator_console.py` and `runtime/tests/test_evidence_unavailable_lifecycle.py` still need a current executable run.
- The complete credential-free Docker watchdog rehearsal still needs a current run against pinned Prometheus 3.13.3 and Grafana 13.2.1.
- The authenticated metrics bridge still needs disposable-project acceptance against a private Cloud Run StageGuard service using a least-privilege invoker identity.
- Historical full-suite failures/errors have not yet been re-triaged; no full-suite green claim exists.

## Single best next step

**Run the new Playwright browser acceptance in a runnable checkout and fix any real DOM/runtime regression it reveals. Once that passes, move to the next production gap rather than adding more frontend scaffolding: validate the authenticated metrics bridge against a disposable private Cloud Run service, proving ADC token acquisition, least-privilege invoker IAM, `/readyz`, `/metrics`, and Prometheus scraping work end to end without exposing credentials.**

## Retained validation baseline

- Local onboarding doctor: 8 passed, 1 expected platform-specific permission test skipped on Windows.
- Focused core/API/UI suite from last executable run: 81/81 passed.
- Historical full suite: 352 tests, 9 failures, 15 errors, 19 skipped; no full-suite green claim.
- Historical live Docker rehearsal: PASS twice consecutively, but it predates the latest acceptance hardening.
- Official Grafana MCP read-only smoke: PASS using `grafana/mcp-grafana:1.3.0` before the latest evidence-availability changes.
- Incident flow baseline: investigate -> diagnose `uplink-b packet loss` -> exact revision approval -> bounded remediation -> telemetry-verified recovered.
