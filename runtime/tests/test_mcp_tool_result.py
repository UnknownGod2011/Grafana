import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from mcp_tool_result import MAX_CONTENT_BLOCKS, MAX_CONTAINER_ITEMS, ToolResultError, validated_tool_content


class DictSubclass(dict):
    pass


class ListSubclass(list):
    pass


class ToolResultTests(unittest.TestCase):
    def test_accepts_meaningful_text_content(self):
        content = validated_tool_content("query_prometheus", {"content": [{"type": "text", "text": "evidence"}]})
        self.assertEqual("evidence", content[0]["text"])

    def test_rejects_error_result(self):
        with self.assertRaisesRegex(ToolResultError, "isError=true"):
            validated_tool_content("query_prometheus", {"isError": True, "content": [{"text": "ignored"}]})

    def test_rejects_hostile_outer_result_subclass(self):
        with self.assertRaisesRegex(ToolResultError, "non-object"):
            validated_tool_content("query_prometheus", DictSubclass(content=[{"text": "evidence"}]))

    def test_rejects_hostile_content_list_subclass(self):
        with self.assertRaisesRegex(ToolResultError, "no evidence content"):
            validated_tool_content("query_prometheus", {"content": ListSubclass([{"text": "evidence"}])})

    def test_rejects_over_limit_content_before_block_inspection(self):
        class ExplodingDict(dict):
            def items(self):
                raise AssertionError("over-limit content must fail before entry traversal")

        content = [ExplodingDict(text="x") for _ in range(MAX_CONTENT_BLOCKS + 1)]
        with self.assertRaisesRegex(ToolResultError, "too many"):
            validated_tool_content("query_prometheus", {"content": content})

    def test_rejects_over_limit_nested_container(self):
        payload = {f"k{i}": i for i in range(MAX_CONTAINER_ITEMS + 1)}
        with self.assertRaisesRegex(ToolResultError, "over-budget"):
            validated_tool_content("query_prometheus", {"content": [{"payload": payload}]})

    def test_rejects_non_finite_numeric_only_payload(self):
        with self.assertRaisesRegex(ToolResultError, "over-budget"):
            validated_tool_content("query_prometheus", {"content": [{"value": float("inf")}]})

    def test_rejects_arbitrary_precision_integer_only_payload(self):
        with self.assertRaisesRegex(ToolResultError, "over-budget"):
            validated_tool_content("query_prometheus", {"content": [{"value": 10 ** 10000}]})

    def test_rejects_metadata_only_block(self):
        with self.assertRaisesRegex(ToolResultError, "over-budget"):
            validated_tool_content("query_prometheus", {"content": [{"type": "text", "mimeType": "application/json"}]})


if __name__ == "__main__":
    unittest.main()
