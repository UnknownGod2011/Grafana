# Grafana MCP evidence safety

StageGuard treats Grafana as an operational evidence plane, not as an untrusted bag of values that can be passed directly into incident policy.

The runtime uses the official Grafana MCP server for read-only Prometheus and Loki access. Local/reference deployment starts `grafana/mcp-grafana:1.4.1` with `--disable-write`, limits enabled tools to `datasource,prometheus,loki`, disables proxied tools, and caps Loki results. Production deployments should preserve the same least-privilege shape even when authentication or transport differs.

## Reviewed dependency baseline

The reference deployment is pinned to official Grafana MCP `v1.4.1`, published **2026-09-11**. The pin is deliberate rather than a floating `latest` dependency.

- Release: https://github.com/grafana/mcp-grafana/releases/tag/v1.4.1
- Upstream repository: https://github.com/grafana/mcp-grafana

The `v1.4.1` release includes a breaking Sift-tool input change: `find_error_pattern_logs` and `find_slow_requests` use `labelSelector` instead of the earlier `labels` map. StageGuard does **not** enable the Sift tool category; its reference MCP process enables only `datasource,prometheus,loki`, retains `--disable-write`, and retains `--disable-proxied`. Therefore that breaking change is outside StageGuard's configured evidence contract.

The preceding `v1.4.0` release added selective `--enable-write-tools` behavior beneath `--disable-write`. StageGuard intentionally does not pass `--enable-write-tools`; server-side writes remain disabled. Any future MCP upgrade must preserve that invariant and must pass the image-pin/least-privilege regression before the pin changes.

Official Grafana documentation:

- MCP introduction: https://grafana.com/docs/grafana/latest/developer-resources/mcp/introduction/
- MCP configuration and read-only controls: https://grafana.com/docs/grafana/latest/developer-resources/mcp/configure/
- MCP tool/RBAC reference: https://grafana.com/docs/grafana/latest/developer-resources/mcp/reference/mcp-tools-table/
- Tool enable/disable and `--disable-write`: https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/oss-mcp/configure/enable-and-disable-tools/

## Live server surface enforcement

Static Compose flags are necessary but not sufficient for a dependency boundary that can evolve upstream. `runtime/mcp_smoke.py` therefore validates the tool surface returned by the running official server before it issues evidence queries.

The smoke requires:

1. `tools/list` to return a well-formed list of uniquely named tool objects;
2. `list_datasources` and `query_prometheus` to be present;
3. **every advertised tool**, including optional Loki/Prometheus/datasource tools, to carry MCP `annotations.readOnlyHint=true`;
4. the configured datasource query to execute successfully after that surface check.

A missing annotation is treated the same as `readOnlyHint=false`: the smoke fails closed. This is intentional. If an upstream image begins registering a newly write-capable or ambiguously annotated tool despite StageGuard's configured flags, the release acceptance should stop before the server is trusted as the evidence plane.

The stdio protocol path is bounded as well. Every JSON-RPC request has a 15-second timeout by default, configurable with `STAGEGUARD_MCP_REQUEST_TIMEOUT_SECONDS` to a positive finite value no greater than 120 seconds. A subprocess that starts but never answers `initialize`, `tools/list`, or `tools/call` therefore fails the smoke instead of hanging a release or operator workflow indefinitely. Invalid timeout configuration fails before the MCP subprocess is trusted. The subprocess is terminated and, if necessary, killed during cleanup so timeout failures do not leave a stranded smoke container.

This runtime assertion is defense in depth. Server-side `--disable-write`, `--disable-proxied`, the narrow enabled categories, and least-privilege Grafana credentials remain required and are not replaced by MCP annotations.

Upstream's contribution guidance explicitly requires write tools to respect `--disable-write`, and the official configuration documents `--enable-write-tools` as the mechanism for selectively re-enabling individual tools. StageGuard does not use that escape hatch.

## Metric evidence contract

`runtime/mcp_metric_client.py` deliberately fails closed at the MCP boundary. A bounded instant query is usable only when all of the following hold:

1. the MCP call itself is not marked as an error;
2. the payload is valid JSON or structured content;
3. the payload has a supported instant-query shape;
4. a vector contains zero or exactly one series — never multiple competing series;
5. a returned sample is numeric and finite;
6. the configured Prometheus datasource UID and PromQL expression are non-empty;
7. the connected MCP server exposes `query_prometheus` and advertises it as read-only.

An empty vector maps to missing evidence (`None`). It is intentionally distinct from zero. Multiple series, malformed values, `NaN`, `+Inf`, `-Inf`, malformed MCP result envelopes, and tool errors raise `McpMetricError` instead of being guessed or coerced into a healthy value.

This is important because Prometheus can legitimately represent special floating-point values. Those encodings may be meaningful in general PromQL, but they are not acceptable as StageGuard safety/diagnostic observations unless a future policy explicitly models them.

## Log evidence contract

`runtime/mcp_log_client.py` applies a similar bounded contract to Loki:

- requested limits are capped;
- responses containing more lines than requested are rejected;
- explicit truncation metadata is preserved;
- legacy responses that exactly fill the requested limit are conservatively treated as potentially truncated;
- labels, parsed fields, and structured metadata must be string maps;
- malformed timestamps, lines, metadata, or MCP envelopes fail closed.

The investigator can use logs as corroboration, but a truncated or malformed log result must never silently become complete evidence.

## Evidence availability and orchestration

`runtime/evidence_errors.py` defines the adapter-neutral `EvidenceUnavailable` contract. Grafana MCP metric/log adapters translate expected MCP transport, protocol, tool, and unusable-result failures into adapter-specific exceptions that also implement this contract.

The investigator catches only `EvidenceUnavailable`. It does **not** catch arbitrary exceptions. This distinction is intentional:

- expected evidence-plane failure becomes a structured `IncidentReport(status="abstain")`;
- the report records only the failed semantic slot in `unavailable_evidence`, for example `causal` or `causal_log`;
- exception text, provider responses, tokens, URLs, datasource details, and raw MCP payloads are never copied into the incident report;
- collection stops at the first unavailable required metric slot, avoiding unnecessary downstream reads from a degraded evidence plane;
- ordinary programming/configuration exceptions such as `TypeError` or invalid policy inputs continue to raise and must be fixed rather than being disguised as an operational abstention.

An evidence-unavailable report always has `hypothesis=None` and `confidence=0.0`. Existing remediation policy requires `status == "diagnosed"` plus an exact matching approval, so even a manually constructed matching approval cannot execute infrastructure mutation from a partial/unavailable evidence report.

`missing_evidence` remains reserved for a successful query that legitimately returns no authoritative sample. `unavailable_evidence` means the evidence source itself could not safely answer. Operators and API consumers can therefore distinguish telemetry absence from evidence-plane failure without receiving sensitive adapter diagnostics.

## Separation from remediation

Grafana MCP credentials are evidence-only. StageGuard remediation uses a separate allowlisted adapter and separate credentials. Gemini briefing/reasoning cannot acquire the remediation credential through the MCP client.

The reference Compose stack also uses server-side `--disable-write`; client-side tool-name restrictions are defense in depth, not the only safety control.

## Regression expectations

Any change to the MCP adapters or investigator should retain tests for:

- ordinary finite vector/scalar parsing;
- empty-vector missing evidence;
- duplicate-series rejection;
- nonnumeric and non-finite rejection;
- malformed MCP envelopes;
- tool errors;
- read-only tool discovery;
- live smoke rejection of malformed/duplicate tool discovery and any advertised tool lacking `readOnlyHint=true`;
- bounded MCP request timeouts and cleanup when a subprocess becomes silent;
- datasource/query input validation;
- Loki result bounds and truncation semantics;
- structured/sanitized evidence-unavailable abstention;
- programming exceptions continuing to propagate;
- evidence-unavailable abstentions being unable to execute remediation even with an otherwise matching approval;
- exact official MCP image pinning and preservation of `--disable-write`, `--disable-proxied`, and the bounded `datasource,prometheus,loki` tool surface.

A live smoke should additionally confirm the official server can query the configured Grafana datasource using the repository-pinned MCP image before a release is considered production-ready.
