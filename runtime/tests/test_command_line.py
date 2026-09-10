import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from command_line import split_command


class CommandLineTests(unittest.TestCase):
    def test_posix_command_preserves_quoted_argument(self):
        self.assertEqual(
            ["docker", "run", "--label", "Stage Guard", "grafana/mcp-grafana:1.3.0"],
            split_command('docker run --label "Stage Guard" grafana/mcp-grafana:1.3.0', windows=False),
        )

    def test_windows_absolute_path_preserves_backslashes(self):
        self.assertEqual(
            [r"C:\Python312\python.exe", "-m", "stageguard_mcp"],
            split_command(r"C:\Python312\python.exe -m stageguard_mcp", windows=True),
        )

    def test_windows_quoted_executable_with_spaces_is_one_argument(self):
        self.assertEqual(
            [r"C:\Program Files\StageGuard\mcp-grafana.exe", "--stdio"],
            split_command(r'"C:\Program Files\StageGuard\mcp-grafana.exe" --stdio', windows=True),
        )

    def test_windows_quoted_regular_argument_has_wrapper_removed(self):
        self.assertEqual(
            ["docker.exe", "run", "--label", "Stage Guard", "mcp-grafana"],
            split_command('docker.exe run --label "Stage Guard" mcp-grafana', windows=True),
        )

    def test_empty_command_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "non-empty"):
            split_command("   ", windows=False)

    def test_unbalanced_quotes_fail_with_bounded_error(self):
        with self.assertRaisesRegex(ValueError, "invalid quoting"):
            split_command('docker run "unterminated', windows=False)


if __name__ == "__main__":
    unittest.main()
