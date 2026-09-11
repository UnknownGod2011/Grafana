# Cloud Run metrics redirect safety

StageGuard's private metrics bridge treats the configured Cloud Run service origin as an exact credential boundary. An authenticated `GET /metrics` must terminate at that origin; the bridge does **not** follow HTTP redirects.

## Why this is required

The bridge obtains a short-lived Google-signed ID token for the configured Cloud Run audience and places it in the upstream `Authorization: Bearer ...` header. Python's `urllib.request` supports redirects by default, and its documentation explicitly distinguishes ordinary request headers from `add_unredirected_header()` headers because ordinary headers can be copied to redirected requests.

For StageGuard, a redirect is never necessary: the operator configures an HTTPS service origin and the bridge derives the exact `/metrics` URL. A `301`, `302`, `303`, `307`, or `308` therefore indicates routing/configuration drift or an unexpected intermediary and must fail closed rather than be trusted.

Official references:

- Python `urllib.request` request-header and redirect behavior: https://docs.python.org/3/library/urllib.request.html
- Google Cloud Run service-to-service authentication: https://cloud.google.com/run/docs/authenticating/service-to-service
- Google Cloud ID-token guidance: https://cloud.google.com/docs/authentication/get-id-token

## Defense in depth

`runtime/cloud_run_metrics_bridge.py` applies two controls:

1. The Cloud Run ID token is installed with `Request.add_unredirected_header()`, so it is explicitly marked as a header that must not be copied to redirected requests.
2. The production opener installs a redirect handler that rejects every upstream redirect. The bridge therefore never makes the redirected request at all.

The second control is stronger and defines the runtime contract. The first protects the credential even if transport behavior is refactored later.

Redirect failure is intentionally indistinguishable from other upstream evidence failures at the bridge HTTP boundary:

- `/readyz` returns sanitized `503`;
- `/metrics` returns sanitized `502`;
- no redirect destination, ID token, provider response, or exception text is returned to Prometheus.

A redirect must become scrape/evidence unavailability, never a positive or healthy StageGuard observation.

## Regression coverage

`runtime/tests/test_cloud_run_metrics_bridge_redirects.py` is credential-free. It proves:

- the bearer credential is stored in the request's unredirected-header collection rather than its ordinary redirectable header collection;
- a real local HTTP server returning `302` cannot cause the production opener to contact the redirect destination;
- consequently the destination receives neither a request nor an authorization credential.

The local HTTP servers exist only to test redirect mechanics. Production StageGuard targets remain restricted to configured HTTPS service origins.
