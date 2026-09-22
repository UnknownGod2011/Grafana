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


def test_unknown_mapping_keys_do_not_execute_str_or_repr():
    class DangerousKey:
        def __hash__(self):
            return 1

        def __str__(self):
            raise AssertionError("str must not be called")

        def __repr__(self):
            raise AssertionError("repr must not be called")

    rendered = safe_diagnostic({DangerousKey(): "datasource unavailable"})
    assert "<DangerousKey-key>" in rendered
    assert "datasource unavailable" in rendered


def test_container_subclasses_are_opaque_and_do_not_execute_hooks():
    class DangerousDict(dict):
        def items(self):
            raise AssertionError("items must not be called")

        def __repr__(self):
            raise AssertionError("repr must not be called")

    class DangerousList(list):
        def __getitem__(self, key):
            raise AssertionError("getitem must not be called")

        def __len__(self):
            raise AssertionError("len must not be called")

        def __repr__(self):
            raise AssertionError("repr must not be called")

    assert safe_diagnostic(DangerousDict(secret="must-not-traverse")) == "'<DangerousDict>'"
    assert safe_diagnostic(DangerousList(["must-not-traverse"])) == "'<DangerousList>'"


def test_scalar_subclasses_are_opaque_and_do_not_execute_stringification():
    class DangerousInt(int):
        def __str__(self):
            raise AssertionError("str must not be called")

        def __repr__(self):
            raise AssertionError("repr must not be called")

    class DangerousStr(str):
        def __str__(self):
            raise AssertionError("str must not be called")

        def __repr__(self):
            raise AssertionError("repr must not be called")

    assert safe_diagnostic(DangerousInt(7)) == "'<DangerousInt>'"
    assert safe_diagnostic(DangerousStr("Bearer must-not-leak")) == "'<DangerousStr>'"


def test_terminal_and_unicode_format_controls_are_neutralized():
    rendered = safe_diagnostic({"message\nspoof": "first\r\nsecond\x1b[31m\u202ehidden\u2066text"})
    assert "\n" not in rendered
    assert "\r" not in rendered
    assert "\x1b" not in rendered
    assert "\u202e" not in rendered
    assert "\u2066" not in rendered
    assert "\\u000a" in rendered
    assert "\\u001b" in rendered
    assert "\\u202e" in rendered
    assert "\\u2066" in rendered


def test_safe_printable_unicode_is_preserved():
    rendered = safe_diagnostic({"message": "München 東京 unavailable"})
    assert "München 東京 unavailable" in rendered


def test_non_secret_operational_context_survives():
    rendered = safe_diagnostic({"code": -32000, "message": "datasource unavailable", "retryable": True})
    assert "-32000" in rendered
    assert "datasource unavailable" in rendered
    assert "True" in rendered
