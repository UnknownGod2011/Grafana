# Cloud Run metrics audience safety

StageGuard's authenticated metrics bridge mints a short-lived Google-signed ID token and sends it to one configured HTTPS `/metrics` target. The token audience and the network destination are related security boundaries: an operator should not be able to accidentally mint a token for one service and send that credential to an unrelated origin merely by combining two configuration values.

## Default rule

`CloudRunMetricsClient` now requires the normalized ID-token audience to equal the normalized metrics target origin by default.

For example, this is accepted without any escape hatch:

```text
target   = https://stageguard-abc.a.run.app
audience = https://stageguard-abc.a.run.app
```

This is rejected during client construction, before any token is minted:

```text
target   = https://metrics-target.example
audience = https://different-audience.example
```

Failing before `token_supplier()` matters: an invalid configuration cannot cause StageGuard to mint a credential that the bridge will not safely deliver.

## Why the audience is security-sensitive

Google Cloud documents ID tokens as audience-bound credentials. For Cloud Run, the audience should identify the service being invoked or a custom audience configured for that receiving service. Google also documents configured custom audiences, including custom-domain-style URL values.

Current official references:

- https://cloud.google.com/run/docs/securing/service-identity
- https://cloud.google.com/run/docs/authenticating/service-to-service
- https://cloud.google.com/run/docs/troubleshooting
- https://cloud.google.com/docs/authentication/token-types

StageGuard therefore prefers configuring Cloud Run with an audience that matches the actual HTTPS target origin. This keeps the token's intended recipient and the network recipient aligned and avoids making cross-origin credential delivery the normal path.

## Explicit cross-origin escape hatch

Some existing deployments can have a legitimate reason to request an audience that differs from the URL contacted by the bridge. This is no longer implicit. The runtime client requires:

```python
CloudRunMetricsClient(
    "https://custom-domain.example",
    audience="https://stageguard-abc.a.run.app",
    allow_cross_origin_audience=True,
)
```

The bridge CLI exposes the corresponding explicit operator acknowledgement:

```bash
python runtime/cloud_run_metrics_bridge.py \
  --target https://custom-domain.example \
  --audience https://stageguard-abc.a.run.app \
  --allow-cross-origin-audience
```

Use this only when the target and audience relationship has been intentionally verified. Prefer a configured Cloud Run custom audience matching the actual target origin when the deployment supports it.

The escape hatch changes only the audience/target equality check. Existing controls still apply:

- the target and audience must each be normalized HTTPS origins;
- the target path is fixed to `/metrics`;
- the bearer token is installed as an unredirected header;
- production HTTP transport rejects redirects;
- the response body must pass StageGuard's safety-sentinel validation;
- bridge failure responses remain sanitized.

## Regression contract

`runtime/tests/test_cloud_run_metrics_bridge_audience_boundary.py` is credential-free and verifies:

- the default audience is exactly the target origin;
- an explicit same-origin audience needs no opt-in;
- a cross-origin audience is rejected before the token supplier is called;
- an explicitly opted-in cross-origin audience is minted for the requested audience but sent only to the configured target;
- the opt-in is a strict boolean rather than a truthy configuration value.

This boundary complements redirect isolation: redirect rejection prevents a token from being replayed to a different destination after a request starts, while audience/target matching prevents an unsafe different destination from being configured silently before the request starts.
