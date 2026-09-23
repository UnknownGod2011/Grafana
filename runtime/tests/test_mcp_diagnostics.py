from mcp_diagnostics import (
    MAX_DIAGNOSTIC_CHARS,
    MAX_DIAGNOSTIC_STRING_CHARS,
    _safe_text,
    safe_diagnostic,
)


def test_redacts_sensitive_mapping_values_recursively():
    payload = {"error": {"Authorization": "Bearer top-secret", "headers": {"X-API-Key": "abc123", "content-type": "application/json"}, "password": "hunter2"}}
    rendered = safe_diagnostic(payload)
    assert "top-secret" not in rendered
    assert "abc123" not in rendered
    assert "hunter2" not in rendered
    assert rendered.count("<redacted>") >= 3
    assert "application/json" in rendered


def test_redacts_credentials_embedded_in_error_strings():
    rendered = safe_diagnostic("request failed: Authorization: Bearer eyJ.secret token=abc123 password=hunter2")
    assert "eyJ.secret" not in rendered
    assert "abc123" not in rendered
    assert "hunter2" not in rendered
    assert "request failed" in rendered


def test_redacts_quoted_assignment_credentials_without_leaking_tail():
    payload = ('request failed: password="correct horse battery staple" ' "secret='alpha beta gamma' " 'api_key="escaped\\\" quote tail" retryable=true')
    rendered = safe_diagnostic(payload)
    for secret_fragment in ("correct", "horse", "battery", "staple", "alpha", "beta", "gamma", "escaped", "quote tail"):
        assert secret_fragment not in rendered
    assert rendered.count("<redacted>") == 3
    assert "retryable=true" in rendered


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
    assert len(rendered) <= MAX_DIAGNOSTIC_CHARS
    assert "truncated" in rendered


def test_string_and_final_diagnostic_caps_include_truncation_marker():
    safe_text = _safe_text("x" * (MAX_DIAGNOSTIC_STRING_CHARS * 4))
    assert len(safe_text) == MAX_DIAGNOSTIC_STRING_CHARS
    assert "truncated" in safe_text

    rendered = safe_diagnostic({f"field-{i}": "x" * 2000 for i in range(32)})
    assert len(rendered) == MAX_DIAGNOSTIC_CHARS
    assert "truncated" in rendered


def test_unknown_objects_do_not_execute_repr():
    class Dangerous:
        def __repr__(self):
            raise AssertionError("repr must not be called")
    assert safe_diagnostic(Dangerous()) == "'<Dangerous>'"


def test_unknown_mapping_keys_do_not_execute_str_or_repr():
    class DangerousKey:
        def __hash__(self): return id(self)
        def __str__(self): raise AssertionError("str must not be called")
        def __repr__(self): raise AssertionError("repr must not be called")
    rendered = safe_diagnostic({DangerousKey(): "datasource unavailable"})
    assert "<DangerousKey-key>" in rendered
    assert "datasource unavailable" in rendered


def test_colliding_opaque_mapping_keys_preserve_each_diagnostic_value():
    class OpaqueKey: pass
    payload = {OpaqueKey(): "first failure", OpaqueKey(): "second failure"}
    rendered = safe_diagnostic(payload)
    assert "<OpaqueKey-key>" in rendered
    assert "<OpaqueKey-key>#2" in rendered
    assert "first failure" in rendered
    assert "second failure" in rendered


def test_container_subclasses_are_opaque_and_do_not_execute_hooks():
    class DangerousDict(dict):
        def items(self): raise AssertionError("items must not be called")
        def __repr__(self): raise AssertionError("repr must not be called")
    class DangerousList(list):
        def __getitem__(self, key): raise AssertionError("getitem must not be called")
        def __len__(self): raise AssertionError("len must not be called")
        def __repr__(self): raise AssertionError("repr must not be called")
    assert safe_diagnostic(DangerousDict(secret="must-not-traverse")) == "'<DangerousDict>'"
    assert safe_diagnostic(DangerousList(["must-not-traverse"])) == "'<DangerousList>'"


def test_scalar_subclasses_are_opaque_and_do_not_execute_stringification():
    class DangerousInt(int):
        def __str__(self): raise AssertionError("str must not be called")
        def __repr__(self): raise AssertionError("repr must not be called")
    class DangerousStr(str):
        def __str__(self): raise AssertionError("str must not be called")
        def __repr__(self): raise AssertionError("repr must not be called")
    assert safe_diagnostic(DangerousInt(7)) == "'<DangerousInt>'"
    assert safe_diagnostic(DangerousStr("Bearer must-not-leak")) == "'<DangerousStr>'"


def test_opaque_type_names_are_display_safe_and_bounded():
    class HostileTypeName: pass
    HostileTypeName.__name__ = "evil\n\x1b[31m\u202espoof-" + ("x" * 500)
    rendered = safe_diagnostic(HostileTypeName())
    assert "\n" not in rendered and "\x1b" not in rendered and "\u202e" not in rendered
    assert "\\u000a" in rendered and "\\u001b" in rendered and "\\u202e" in rendered
    assert "truncated" in rendered
    assert len(rendered) < 180


def test_opaque_mapping_key_type_names_are_display_safe_and_bounded():
    class HostileKey: pass
    HostileKey.__name__ = "key\r\n\u2066spoof-" + ("y" * 500)
    rendered = safe_diagnostic({HostileKey(): "datasource unavailable"})
    assert "\n" not in rendered and "\r" not in rendered and "\u2066" not in rendered
    assert "\\u000d" in rendered and "\\u000a" in rendered and "\\u2066" in rendered
    assert "datasource unavailable" in rendered


def test_terminal_and_unicode_format_controls_are_neutralized():
    rendered = safe_diagnostic({"message\nspoof": "first\r\nsecond\x1b[31m\u202ehidden\u2066text"})
    assert "\n" not in rendered and "\r" not in rendered and "\x1b" not in rendered
    assert "\u202e" not in rendered and "\u2066" not in rendered
    assert "\\u000a" in rendered and "\\u001b" in rendered and "\\u202e" in rendered and "\\u2066" in rendered


def test_safe_printable_unicode_is_preserved():
    assert "München 東京 unavailable" in safe_diagnostic({"message": "München 東京 unavailable"})


def test_non_secret_operational_context_survives():
    rendered = safe_diagnostic({"code": -32000, "message": "datasource unavailable", "retryable": True})
    assert "-32000" in rendered
    assert "datasource unavailable" in rendered
    assert "True" in rendered
