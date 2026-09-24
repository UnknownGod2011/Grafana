#!/usr/bin/env python3
"""Create/reuse the local read-only Grafana service-account token for MCP.

Zero third-party dependencies. The script refuses to bootstrap a remote Grafana
instance unless STAGEGUARD_ALLOW_REMOTE_BOOTSTRAP=1 is explicitly set, and remote
credential bootstrap is HTTPS-only.
"""
from __future__ import annotations

import base64
import ipaddress
import json
import os
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

GRAFANA_URL = os.getenv("STAGEGUARD_GRAFANA_URL", "http://localhost:3000").rstrip("/")
ADMIN_USER = os.getenv("STAGEGUARD_GRAFANA_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("STAGEGUARD_GRAFANA_ADMIN_PASSWORD", "stageguard-local-only")
ACCOUNT_NAME = os.getenv("STAGEGUARD_MCP_SERVICE_ACCOUNT", "stageguard-mcp")
TOKEN_TTL = int(os.getenv("STAGEGUARD_MCP_TOKEN_TTL_SECONDS", "86400"))
TOKEN_PATH = Path(os.getenv("STAGEGUARD_MCP_TOKEN_FILE", "runtime/.secrets/grafana-mcp-token"))
DATASOURCE_UID = os.getenv("STAGEGUARD_DATASOURCE_UID", "stageguard-prometheus")


def _is_loopback_host(host: str) -> bool:
    """Recognize localhost and all literal IPv4/IPv6 loopback addresses only."""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _request(path: str, *, method: str = "GET", payload: dict | None = None, token: str | None = None) -> tuple[int, object]:
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        raw = f"{ADMIN_USER}:{ADMIN_PASSWORD}".encode()
        headers["Authorization"] = "Basic " + base64.b64encode(raw).decode()
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(GRAFANA_URL + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            body = response.read().decode().strip()
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode().strip()
        try:
            detail: object = json.loads(body) if body else {}
        except json.JSONDecodeError:
            detail = body
        return exc.code, detail


def _validate_bootstrap_target(url: str, *, allow_remote: bool) -> None:
    """Fail closed before admin credentials can be sent to an unsafe target."""
    try:
        parsed = urllib.parse.urlsplit(url)
        # Accessing port is intentionally part of validation: urllib defers
        # malformed/out-of-range port errors until this property is read.
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Grafana URL is malformed") from exc
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not host or parsed.username is not None or parsed.password is not None:
        raise ValueError("Grafana URL must be an http(s) origin without embedded credentials")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("Grafana URL must be an origin without a path, query, or fragment")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("Grafana URL port is invalid")

    is_loopback = _is_loopback_host(host)
    if not is_loopback and not allow_remote:
        raise ValueError(
            f"Refusing to create credentials on remote Grafana host {host!r}. "
            "Set STAGEGUARD_ALLOW_REMOTE_BOOTSTRAP=1 only after verifying the target."
        )
    if not is_loopback and parsed.scheme != "https":
        raise ValueError("Remote Grafana credential bootstrap requires HTTPS")


def _guard_target() -> None:
    try:
        _validate_bootstrap_target(GRAFANA_URL, allow_remote=os.getenv("STAGEGUARD_ALLOW_REMOTE_BOOTSTRAP") == "1")
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


def _wait_for_grafana(timeout_seconds: int = 90) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(GRAFANA_URL + "/api/health", timeout=3) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(2)
    raise SystemExit(f"Grafana did not become healthy at {GRAFANA_URL} within {timeout_seconds}s")


def _find_or_create_account() -> int:
    query = urllib.parse.urlencode({"perpage": 100, "page": 1, "query": ACCOUNT_NAME})
    status, body = _request(f"/api/serviceaccounts/search?{query}")
    if status != 200 or not isinstance(body, dict):
        raise SystemExit(f"Unable to search Grafana service accounts: HTTP {status}: {body}")
    for account in body.get("serviceAccounts", []):
        if account.get("name") == ACCOUNT_NAME:
            if account.get("role") != "Viewer" or account.get("isDisabled"):
                raise SystemExit(
                    f"Existing service account {ACCOUNT_NAME!r} is not an enabled Viewer; "
                    "refusing to broaden or mutate permissions automatically."
                )
            return int(account["id"])

    status, body = _request(
        "/api/serviceaccounts",
        method="POST",
        payload={"name": ACCOUNT_NAME, "role": "Viewer", "isDisabled": False},
    )
    if status != 201 or not isinstance(body, dict) or "id" not in body:
        raise SystemExit(f"Unable to create Grafana service account: HTTP {status}: {body}")
    return int(body["id"])


def _token_is_valid(token: str) -> bool:
    status, _ = _request(f"/api/datasources/uid/{urllib.parse.quote(DATASOURCE_UID)}", token=token)
    return status == 200


def _write_token(token: str) -> None:
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(token.strip() + "\n", encoding="utf-8")
    TOKEN_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)


def main() -> None:
    _guard_target()
    _wait_for_grafana()

    if TOKEN_PATH.exists():
        existing = TOKEN_PATH.read_text(encoding="utf-8").strip()
        if existing and _token_is_valid(existing):
            print(f"Reusing valid MCP service-account token at {TOKEN_PATH}")
            return

    account_id = _find_or_create_account()
    token_name = f"stageguard-local-{int(time.time())}"
    status, body = _request(
        f"/api/serviceaccounts/{account_id}/tokens",
        method="POST",
        payload={"name": token_name, "secondsToLive": TOKEN_TTL},
    )
    if status not in {200, 201} or not isinstance(body, dict) or not body.get("key"):
        raise SystemExit(f"Unable to create Grafana service-account token: HTTP {status}: {body}")
    _write_token(str(body["key"]))
    print(f"Created short-lived Viewer token for {ACCOUNT_NAME!r} at {TOKEN_PATH}")
    print("Token value was intentionally not printed.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)