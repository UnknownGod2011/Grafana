# Grafana MCP evidence safety

StageGuard treats Grafana as an operational evidence plane, not as an untrusted bag of values that can be passed directly into incident policy.

The runtime uses the official Grafana MCP server for read-only Prometheus and Loki access. Local/reference deployment starts `grafana/mcp-grafana:1.3.0` with `--disable-write`, limits enabled tools to `datasource,prometheus,loki`, disables proxied tools, and caps Loki results. Production deployments should preserve the same least-privilege shape even when authentication or transport differs.

Official Grafana documentation:

- MCP introduction: https://grafana.com/docs/grafana/latest/developer-resources/mcp/introduction/
- MCP configuration and read-only controls: https://grafana.com/docs/grafana/latest/developer-resources/mcp/configure/
- MCP tool/RBAC reference: https://grafana.com/docs/grafana/latest/developer-resources/mcp/reference/mcp-tools-table/
- Tool enable/disable and `--disable-write`: https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/oss-mcp/configure/enable-and-disable-tools/

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

## Separation from remediation

Grafana MCP credentials are evidence-only. StageGuard remediation uses a separate allowlisted adapter and separate credentials. Gemini briefing/reasoning cannot acquire the remediation credential through the MCP client.

The reference Compose stack also uses server-side `--disable-write`; client-side tool-name restrictions are defense in depth, not the only safety control.

## Regression expectations

Any change to the MCP adapters should retain tests for:

- ordinary finite vector/scalar parsing;
- empty-vector missing evidence;
- duplicate-series rejection;
- nonnumeric and non-finite rejection;
- malformed MCP envelopes;
- tool errors;
- read-only tool discovery;
- datasource/query input validation;
- Loki result bounds and truncation semantics.

A live smoke should additionally confirm the official server can query the configured Grafana datasource using the repository-pinned MCP image before a release is considered production-ready.
