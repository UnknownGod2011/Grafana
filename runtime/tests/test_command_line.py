import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from command_line import split_command


class CommandLineTests(unittest.TestCase):
    def test_posix_command_preserves_quoted_argument(self):
        self.assertEqual(
            [
                "docker",
                "run",
                "--label",
                "Stage Guard",
                "grafana/mcp-grafana:1.4.1",
                "-t",
                "stdio",
            ],
            split_command(
                'docker run --label "Stage Guard" grafana/mcp-grafana:1.4.1 -t stdio',
                windows=False,
            ),
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

    def test_native_binary_may_use_documented_stdio_default(self):
        self.assertEqual(
            ["mcp-grafana", "--disable-write"],
            split_command("mcp-grafana --disable-write", windows=False),
        )

    def test_repository_compose_launcher_is_allowed_without_inline_transport(self):
        self.assertEqual(
            ["docker", "compose", "run", "--rm", "-T", "mcp"],
            split_command("docker compose run --rm -T mcp", windows=False),
        )

    def test_direct_official_docker_image_requires_explicit_stdio(self):
        with self.assertRaisesRegex(ValueError, "explicitly set -t stdio"):
            split_command("docker run --rm grafana/mcp-grafana:1.4.1", windows=False)

    def test_direct_official_docker_digest_requires_explicit_stdio(self):
        with self.assertRaisesRegex(ValueError, "explicitly set -t stdio"):
            split_command("docker run --rm grafana/mcp-grafana@sha256:abc123", windows=False)

    def test_explicit_stdio_transport_forms_are_allowed(self):
        commands = (
            "mcp-grafana -t stdio",
            "mcp-grafana --transport stdio",
            "mcp-grafana -t=stdio",
            "mcp-grafana --transport=stdio",
            "docker run --rm grafana/mcp-grafana:1.4.1 -t stdio",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertTrue(split_command(command, windows=False))

    def test_network_transports_are_rejected(self):
        commands = (
            "mcp-grafana -t sse",
            "mcp-grafana --transport sse",
            "mcp-grafana -t=streamable-http",
            "mcp-grafana --transport=streamable-http",
            "docker run --rm grafana/mcp-grafana:1.4.1 --transport sse",
        )
        for command in commands:
            with self.subTest(command=command):
                with self.assertRaisesRegex(ValueError, "stdio transport"):
                    split_command(command, windows=False)

    def test_unknown_non_stdio_transport_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "requires Grafana MCP stdio transport"):
            split_command("mcp-grafana --transport future-transport", windows=False)

    def test_duplicate_transport_declarations_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "transport at most once"):
            split_command("mcp-grafana -t stdio --transport=stdio", windows=False)

    def test_transport_flag_requires_value(self):
        with self.assertRaisesRegex(ValueError, "transport flag requires a value"):
            split_command("mcp-grafana --transport", windows=False)

    def test_empty_command_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "non-empty"):
            split_command("   ", windows=False)

    def test_unbalanced_quotes_fail_with_bounded_error(self):
        with self.assertRaisesRegex(ValueError, "invalid quoting"):
            split_command('docker run "unterminated', windows=False)


if __name__ == "__main__":
    unittest.main()
