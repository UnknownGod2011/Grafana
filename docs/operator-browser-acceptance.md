# Operator browser safety acceptance

StageGuard has an optional real-browser acceptance test for the fail-closed evidence-plane-unavailable state:

```bash
python -m pip install playwright
python -m playwright install chromium
python -m unittest runtime.tests.test_operator_browser_evidence_unavailable
```

The Playwright dependency is deliberately **not** a runtime dependency. Production StageGuard remains dependency-free at the browser layer; Playwright is only needed by contributors who want to execute this browser acceptance locally or in a disposable validation environment.

## What the test proves

`runtime/tests/test_operator_browser_evidence_unavailable.py` starts the real authenticated StageGuard HTTP server with `StaticBearerIdentityProvider`, then creates a real incident through `IncidentService`. The metric adapter returns the first symptom sample and raises `EvidenceUnavailable` on the required causal read with deliberately sensitive sentinel text embedded in the exception.

Headless Chromium then loads the shipped `/console` and authenticated `/assets/operator.js`. The test waits for the actual cockpit to fetch `/v1/incident` and verifies all of the following in rendered DOM state:

- `Evidence plane unavailable` is visible;
- the deterministic hypothesis is `Not established`;
- Gemini briefing is disabled;
- revision entry is disabled;
- approval is disabled;
- execution is disabled;
- the remediation adapter has received zero calls;
- the authoritative cockpit and first-viewport proof layer both report evidence unavailability;
- provider-token, provider-endpoint, and secret sentinels from the thrown exception are absent from both rendered text and serialized page HTML.

This is intentionally stronger than string-level asset tests. It validates the complete browser-facing chain:

`EvidenceUnavailable -> IncidentService abstention -> authenticated API JSON -> shipped JavaScript -> DOM safety state`

## Failure interpretation

A failure in this test is a release-blocking operator-safety regression if any of the following occurs:

1. an abstained evidence-plane incident enables an advisory or mutation control;
2. the browser asserts a root cause after required evidence became unavailable;
3. the remediation adapter is invoked;
4. provider failure detail reaches the DOM;
5. the judge/proof layer disagrees with the authoritative cockpit state.

If Playwright is not installed, `unittest` skips this optional module rather than making the core test suite fail. This keeps normal local/free development lightweight while preserving an executable browser acceptance path for release validation.
