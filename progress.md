# StageGuard Progress

## Current status

StageGuard is a personal open-source incident commander for live media workflows. The executable safety core now covers:

`strict telemetry mapping → eight-read metric preflight → metric activation pin → one bounded Loki preflight → Loki contract/datasource activation pin → official Grafana MCP Prometheus + Loki adapters → six-read metric diagnosis → mandatory production Loki corroboration → authenticated IncidentService → optional revision-bound Gemini advisory briefing → revision-bound approval → governed allowlisted remediation → credential-isolated HTTPS transport → two-read telemetry recovery verification → bounded local or Google Cloud Logging audit`

Core invariants:

- Grafana remains the operational evidence plane; infrastructure write credentials remain separate.
- Production Prometheus and Loki datasource identities and semantic contracts are pinned by expiring activation artifacts.
- Production investigation uses six metric reads first and one bounded Loki corroboration query only after metrics independently diagnose.
- Missing, truncated, or scope-inconsistent Loki evidence forces abstention.
- Gemini is advisory only and cannot mutate diagnosis, approval, remediation, or recovery state.
- Gemini briefing requests must match the exact current incident ID and evidence revision.
- Production Google identity is derived from a verified signed IAP JWT `sub` claim, not unsigned convenience headers or request JSON.
- Approval is tied to the exact evidence revision, single-use, and invalidated by fresh investigation.
- Production writes require explicit startup opt-in plus separate process-owned endpoint/credential configuration.
- Action acceptance is never recovery; Grafana telemetry must prove consecutive healthy samples.
- Cloud audit receives only bounded structured lifecycle metadata and rejects secret/query/raw-evidence shaped fields.

## Completed milestones

- Deterministic broadcast telemetry simulator + Prometheus + provisioned Grafana local stack.
- Opt-in pinned official `grafana/mcp-grafana:1.1.0` path with write tools disabled.
- Deterministic four-class incident investigation with exactly six metric reads.
- MCP Prometheus adapter with fail-closed parsing and query provenance.
- Approval-gated remediation with distinct write boundary and telemetry-only recovery proof.
- Strict configurable production telemetry mapping and eight-slot readiness preflight.
- SHA-256 pinned expiring metric activation for non-demo profiles.
- Bounded semantic Loki corroboration using official Grafana MCP `query_loki_logs`.
- Separate Loki activation pinning semantic log contract and actual Loki datasource identity.
- Credential-isolated HTTPS remediation transport and loopback idempotency receiver.
- Bounded Gemini incident-commander layer with strict structured context/output validation.
- Revision-bound authenticated Gemini briefing endpoint with non-sensitive digest auditing.
- Verified Google IAP identity provider using signed JWT assertions and stable subject claims.
- Bounded Google Cloud Logging lifecycle audit sink with explicit production bootstrap selection.
- Google Cloud deployment guide for IAP + centralized audit boundary.

## Prior handoff

The previous run connected the bounded Gemini commander to the authenticated lifecycle through an exact `incident_id + revision` advisory endpoint. The highest-value remaining production boundary was operator identity and durable centralized audit.

## Run log — 2026-09-07 — Google IAP identity + Cloud Logging audit

### Inspected at start

Read this `progress.md` completely before selecting work. Then inspected current `main`, specifically:

- `runtime/api.py`
- `runtime/identity.py`
- `runtime/incident_service.py`
- `runtime/bootstrap.py`
- `runtime/tests/test_identity.py`
- `runtime/production_remediation.py`
- root `README.md`

Researched current official Google documentation for IAP identity, signed-header verification, Cloud Run IAP, and Cloud Logging. The key security requirement confirmed by Google is that applications must validate `X-Goog-IAP-JWT-Assertion`; `X-Goog-Authenticated-User-Id` and `X-Goog-Authenticated-User-Email` are compatibility headers and must not be relied on as the security mechanism if IAP can be bypassed.

### Exact changes made

Updated `runtime/identity.py`:

- added `GoogleIapIdentityProvider` as a production-capable identity boundary;
- accepts only the signed `X-Goog-IAP-JWT-Assertion` header;
- verifies the JWT through Google's documented Python `google.oauth2.id_token.verify_token` path using the IAP public-key URL and the exact configured audience;
- independently requires issuer `https://cloud.google.com/iap`, exact audience match, and a non-empty stable `sub` claim;
- derives StageGuard actor identity from `sub`, not email and not unsigned Google identity headers;
- bounds assertion and subject size;
- returns generic authentication failures instead of leaking verifier/signature details;
- imports `google-auth` lazily so local/free operation is unaffected.

Added `runtime/cloud_audit.py`:

- added `GoogleCloudLoggingAuditSink` with lazy `google-cloud-logging` import and ADC-compatible construction;
- emits one `stageguard.audit.v1` structured entry per `AuditEvent` through `logger.log_struct`;
- validates event envelope and total serialized size before writing;
- rejects payload keys shaped like authorization, credentials, passwords, secrets, tokens, endpoints, prompts, PromQL, LogQL, or raw log bodies;
- rejects binary/list/set payloads, excessive nesting, excessive field counts, and oversized strings;
- allows exactly one bounded mapping level so existing safe `action_metadata` from production remediation continues to audit correctly;
- does not claim Cloud Logging is immutable; stronger retention/lock remains a deployment policy.

Updated `runtime/bootstrap.py`:

- added explicit identity modes: `auto`, `local`, `bearer`, `iap`;
- added `STAGEGUARD_IAP_AUDIENCE` / `--iap-audience-env` configuration;
- auto mode prefers IAP when an IAP audience is configured, otherwise preserves loopback-local/static-bearer behavior;
- non-loopback local identity remains refused;
- added audit backends `jsonl` and `cloud-logging`;
- added Cloud Logging project-env/log-name configuration;
- selecting IAP or Cloud Logging requires the matching optional dependency and fails rather than silently downgrading;
- Gemini/remediation opt-ins remain independent.

Updated tests:

- `runtime/tests/test_identity.py` now covers signed IAP identity, spoofed unsigned Google headers, verifier failure redaction, issuer/audience/subject drift, invalid audience configuration, and oversized assertions;
- added `runtime/tests/test_cloud_audit.py` covering structured writes, deterministic envelope, safe remediation metadata, blocked sensitive/query keys at both supported depths, deep nesting/collection rejection, size bounds, and invalid event envelopes.

Documentation:

- added `GOOGLE_CLOUD_DEPLOYMENT.md` with Cloud Run/IAP trust model, exact audience form, least-privilege audit guidance, failure behavior, and deployment checklist;
- updated root `README.md` so verified IAP identity and bounded centralized Cloud Logging audit are part of the current executable architecture rather than future roadmap items.

### Official references used

- Google IAP identity: https://cloud.google.com/iap/docs/identity-howto
- Google IAP signed-header verification: https://cloud.google.com/iap/docs/signed-headers-howto
- IAP for Cloud Run: https://cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run
- Cloud Logging Python: https://cloud.google.com/logging/docs/write-query-log-entries-python
- Cloud Logging Python client reference: https://cloud.google.com/python/docs/reference/logging/latest

### Commits produced this run

- `376bdc61` — add verified Google IAP identity provider
- `610f22cd` — add bounded Cloud Logging audit sink
- `954b098a` — wire IAP identity and Cloud Logging audit into bootstrap
- `b2ef0a43` — test signed IAP identity boundary
- `f3469b83` — test bounded Cloud Logging audit sink
- `de66f878` — allow bounded remediation metadata in audit
- `2f35e1bc` — cover bounded nested remediation audit metadata
- `231b3ab5` — document IAP and Cloud Logging production boundary
- `b43ce378` — document production IAP identity and durable audit

### Tests / checks / results

No GitHub Actions workflow was created, triggered, or rerun.

This automation environment still does not expose a runnable checkout of the repository, and prior direct `git clone` attempts fail DNS resolution for `github.com`. Therefore the repository Python suite was not executed in this run and is **not claimed as passing**.

A local Python parser check was used for the only non-obvious syntax form introduced in the identity tests (`lambda *args, keyword_default=...`), which is valid Python syntax. The changed repository files were also re-read through the authenticated GitHub connector while reviewing integration compatibility.

No Grafana, Loki, Gemini, IAP, Cloud Logging, operator, or remediation credentials were used.

### Decisions made

1. **Signed IAP JWT is the sole Google production identity evidence.** Unsigned compatibility headers are ignored for authentication.
2. **Stable `sub` is the audit actor identifier.** Email is unnecessary PII for StageGuard's authorization/audit boundary.
3. **IAP audience is process configuration.** It cannot be supplied by HTTP clients.
4. **Google dependencies remain lazy.** Local/open-source operation stays credential-free until an operator explicitly selects Google production modes.
5. **Cloud audit is bounded before provider I/O.** StageGuard does not send arbitrary messages or raw evidence to Cloud Logging.
6. **Existing remediation metadata remains auditable.** The serializer permits one bounded scalar mapping level rather than breaking the production remediation lifecycle.
7. **Cloud Logging is centralized/durable, not inherently immutable.** Long-retention or locked storage is documented as an external deployment control rather than overstated in code.
8. **Static bearer remains fallback, not the preferred Google Cloud production path.** IAP is now the documented internet-facing deployment choice.

### Current blockers / unknowns

- The deterministic Python suite remains unexecuted in this automation environment because no runnable checkout is available here.
- The IAP verifier has not yet been exercised against a real Cloud Run service and real signed IAP assertion.
- The Cloud Logging sink has not yet been exercised against a real Google Cloud project/service account.
- Full Docker → Grafana → official MCP metric/Loki acceptance remains unverified on a Docker-capable host.
- Optional Gemini has not yet been exercised against a live Vertex AI project/ADC session.
- No operator web console exists yet.
- No checked-in deployable Cloud Run image/manifest currently packages the full incident API plus optional Google dependencies; the existing runtime Dockerfile is simulator-focused.

## Single best next step

**Package the actual incident API as a production Cloud Run service without weakening the current boundaries: add a dedicated API Dockerfile/requirements or equivalent reproducible image, non-root runtime, explicit health check, environment contract, and a deployment manifest/script that selects `--identity-mode iap` + `--audit-backend cloud-logging` while keeping remediation disabled by default. Add credential-free container/config tests where possible. This turns the newly implemented identity/audit boundary into a deployable artifact rather than documentation-only composition.**
