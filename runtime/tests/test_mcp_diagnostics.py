from mcp_diagnostics import safe_diagnostic


def test_redacts_sensitive_mapping_values_recursively():
    payload = {
        "error": {
            "Authorization": "Bearer top-secret",
            "headers": {"X-API-Key": "abc123", "content-type": "application/json"},
            "password": "hunter2",
        }
    }
    rendered = safe_diagnostic(payload)
    assert "top-secret" not in rendered
    assert "abc123" not in rendered
    assert "hunter2" not in rendered
    assert rendered.count("<redacted>") >= 3
    assert "application/json" in rendered


def test_redacts_credentials_embedded_in_error_strings():
    payload = "request failed: Authorization: Bearer eyJ.secret token=abc123 password=hunter2"
    rendered = safe_diagnostic(payload)
    assert "eyJ.secret" not in rendered
    assert "abc123" not in rendered
    assert "hunter2" not in rendered
    assert "request failed" in rendered


def test_redacts_basic_auth_and_url_passwords():
    rendered = safe_diagnostic("Basic dXNlcjpwYXNz https://alice:swordfish@example.test/api")
    assert "dXNlcjpwYXNz" not in rendered
    assert "swordfish" not in rendered
    assert "example.test" in rendered


def test_bounds_nested_and_wide_attacker_controlled_payloads():
    nested = "leaf"
    for _ in range(20):
        nested = {"child": nested}
    payload = {f"field-{i}": "x" * 1000 for i in range(100)}
    payload["nested"] = nested
    rendered = safe_diagnostic(payload)
    assert len(rendered) < 2200
    assert "truncated" in rendered


def test_unknown_objects_do_not_execute_repr():
    class Dangerous:
        def __repr__(self):
            raise AssertionError("repr must not be called")

    assert safe_diagnostic(Dangerous()) == "'<Dangerous>'"


def test_non_secret_operational_context_survives():
    rendered = safe_diagnostic({"code": -32000, "message": "datasource unavailable", "retryable": True})
    assert "-32000" in rendered
    assert "datasource unavailable" in rendered
    assert "True" in rendered
