import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from mcp_jsonrpc_identity import ResponseIdentityError, assert_integer_response_id


class IntSubclass(int):
    pass


class JsonRpcResponseIdentityTests(unittest.TestCase):
    def test_exact_integer_id_is_accepted(self):
        assert_integer_response_id(1, 1)
        assert_integer_response_id(42, 42)

    def test_boolean_true_cannot_alias_integer_one(self):
        with self.assertRaises(ResponseIdentityError):
            assert_integer_response_id(True, 1)

    def test_boolean_false_is_not_an_integer_response_id(self):
        with self.assertRaises(ResponseIdentityError):
            assert_integer_response_id(False, 1)

    def test_numeric_string_is_rejected(self):
        with self.assertRaises(ResponseIdentityError):
            assert_integer_response_id("1", 1)

    def test_integer_subclass_is_rejected(self):
        with self.assertRaises(ResponseIdentityError):
            assert_integer_response_id(IntSubclass(1), 1)

    def test_wrong_integer_is_rejected(self):
        with self.assertRaises(ResponseIdentityError):
            assert_integer_response_id(2, 1)

    def test_invalid_expected_id_fails_programmer_contract(self):
        for value in (True, 0, -1, "1"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    assert_integer_response_id(value, 1)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
