# Grafana MCP security boundary

StageGuard treats Grafana as its runtime evidence plane. The MCP connection therefore has access to operational telemetry and must be deployed with the same care as any production observability credential.

## Supported StageGuard mode

StageGuard's production and smoke launchers use the official `grafana/mcp-grafana` server over **stdio only**. The MCP process is a child process of StageGuard; no MCP listener is exposed on a TCP port. Keep this invariant unless a separately authenticated network deployment is deliberately designed, reviewed, and tested.

Use a dedicated Grafana service account with the minimum read permissions needed by the StageGuard telemetry contract. Do not reuse remediation/provider credentials. StageGuard's HTTP API does not accept Grafana URLs, datasource UIDs, PromQL, LogQL, MCP transport flags, or Grafana credentials from callers.

## Credential rules

- Supply the Grafana service-account token through the existing secret/file mechanism; never commit it or place it in command-line arguments.
- Give the identity read access only to the dashboards/datasources/resources StageGuard needs.
- Keep remediation credentials in the remediation adapter boundary. The Grafana MCP process must never receive them.
- Rotate the Grafana credential independently of StageGuard incident state.
- Treat child-process environment dumps, debug logs, crash reports, and support bundles as potentially sensitive; do not emit token values.

## Transport policy

Current upstream Grafana documentation supports `stdio`, SSE, and Streamable HTTP. It also documents `--server-auth-token` / `MCP_GRAFANA_SERVER_TOKEN` for authenticating callers on network transports. StageGuard nevertheless remains stdio-only because it does not need a remotely callable MCP surface. A network transport would add another authenticated service boundary without improving the current architecture.

If a future deployment genuinely requires remote MCP, it must be an explicit new StageGuard mode rather than a launcher flag passthrough. At minimum it must require caller authentication, a non-public bind/network policy, TLS where traffic leaves a trusted local boundary, least-privilege Grafana RBAC, fixed tool/query policy, bounded timeouts, and regression tests proving unauthenticated callers cannot invoke tools. Do not silently fall back to an unauthenticated listener.

## Read-only evidence policy

The upstream MCP server exposes both read and write-capable Grafana tools. StageGuard must not treat availability of a tool as authorization to use it. Runtime investigation is policy-owned: metric and Loki contracts are activated ahead of time, datasource identity is pinned, and callers cannot submit arbitrary queries. Grafana evidence is used to diagnose and later verify recovery; remediation is performed through the separate governed remediation adapter.

## Production checklist

1. Use the official Grafana MCP implementation and a reviewed/pinned release.
2. Launch it with StageGuard's stdio-only launcher.
3. Use a dedicated least-privilege Grafana identity.
4. Run `python scripts/stageguard_doctor.py runtime/telemetry.example.json` without exposing token contents.
5. Run the live MCP smoke and metric/Loki activation preflight against the target Grafana instance.
6. Confirm remediation credentials are absent from the MCP process environment.
7. Confirm StageGuard's public/operator HTTP listeners do not expose an MCP endpoint.
8. Re-run the smoke when changing the pinned MCP release or Grafana RBAC.

## Upstream references

Reviewed 2026-09-15:

- Grafana, **Introduction to the Grafana MCP server**: https://grafana.com/docs/grafana/latest/developer-resources/mcp/introduction/
- Grafana, **Transports and addresses**: https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/oss-mcp/configure/transports-and-addresses/
- Grafana, **Command-line flags** (including network caller authentication): https://grafana.com/docs/grafana/latest/developer-resources/mcp/configure/command-line-flags/
- Grafana, **Install with Docker**: https://grafana.com/docs/grafana-cloud/ai-tools/mcp-servers/oss-mcp/set-up/install-with-docker/

These links describe upstream capabilities; StageGuard's supported deployment policy is intentionally narrower.