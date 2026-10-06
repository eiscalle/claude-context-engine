"""Tests that spawned Agent SDK sessions cannot reach tools beyond their job.

The CLI started by the SDK loads the user's settings: permission mode (often
bypassPermissions), plugins with their subagents, and MCP servers.
`allowed_tools` only pre-approves tools, so a flush agent without an explicit
`tools=` list could run Bash or launch subagents from the conversation it was
asked to summarise.
"""

from __future__ import annotations

import ast
import runpy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
CONFIG = runpy.run_path(str(SCRIPTS_DIR / "config.py"))

TEXT_ONLY_SCRIPTS = ("flush.py", "lint.py")
FILE_TOOL_SCRIPTS = ("compile.py", "ingest.py")
AGENT_SCRIPTS = TEXT_ONLY_SCRIPTS + FILE_TOOL_SCRIPTS + ("query.py",)


def _options_keywords(script_name: str) -> dict[str, ast.expr]:
    tree = ast.parse((SCRIPTS_DIR / script_name).read_text(encoding="utf-8"), filename=script_name)
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "ClaudeAgentOptions"
    ]
    assert len(calls) == 1, f"expected one SDK options call in {script_name}"
    return {keyword.arg: keyword.value for keyword in calls[0].keywords}


def _cli_command(**option_kwargs) -> list[str]:
    from claude_agent_sdk import ClaudeAgentOptions
    from claude_agent_sdk._internal.transport.subprocess_cli import SubprocessCLITransport

    options = ClaudeAgentOptions(cli_path="/bin/true", **option_kwargs)
    return SubprocessCLITransport(prompt="summarise", options=options)._build_command()


class AgentOptionsSourceTests(unittest.TestCase):
    def test_every_agent_lists_its_tools_and_drops_user_mcp_servers(self) -> None:
        for script_name in AGENT_SCRIPTS:
            keywords = _options_keywords(script_name)
            self.assertIn("tools", keywords, f"{script_name} must pass tools=")
            self.assertIsInstance(keywords.get("extra_args"), ast.Name, script_name)
            self.assertEqual(keywords["extra_args"].id, "AGENT_CLI_ARGS", script_name)

    def test_text_only_agents_have_no_tools_and_no_bypass(self) -> None:
        for script_name in TEXT_ONLY_SCRIPTS:
            keywords = _options_keywords(script_name)
            self.assertEqual(ast.literal_eval(keywords["tools"]), [], script_name)
            self.assertEqual(ast.literal_eval(keywords["permission_mode"]), "default", script_name)

    def test_file_agents_see_only_file_tools(self) -> None:
        for script_name in FILE_TOOL_SCRIPTS:
            keywords = _options_keywords(script_name)
            self.assertIsInstance(keywords["tools"], ast.Name, script_name)
            self.assertEqual(keywords["tools"].id, "FILE_TOOLS", script_name)

    def test_file_tools_exclude_shell_and_subagents(self) -> None:
        self.assertEqual(set(CONFIG["FILE_TOOLS"]), {"Read", "Write", "Edit", "Glob", "Grep"})


@unittest.skipUnless(
    any(Path(p, "claude_agent_sdk").is_dir() for p in sys.path if p), "claude_agent_sdk is not installed"
)
class AgentCliCommandTests(unittest.TestCase):
    def test_text_only_agent_command_disables_every_tool(self) -> None:
        command = _cli_command(tools=[], permission_mode="default", extra_args=CONFIG["AGENT_CLI_ARGS"])

        tools_value = command[command.index("--tools") + 1]
        self.assertEqual(tools_value, "")
        self.assertEqual(command[command.index("--permission-mode") + 1], "default")
        self.assertIn("--strict-mcp-config", command)

    def test_file_agent_command_lists_only_file_tools(self) -> None:
        command = _cli_command(
            tools=CONFIG["FILE_TOOLS"],
            allowed_tools=CONFIG["FILE_TOOLS"],
            permission_mode="bypassPermissions",
            extra_args=CONFIG["AGENT_CLI_ARGS"],
        )

        self.assertEqual(command[command.index("--tools") + 1], "Read,Write,Edit,Glob,Grep")
        self.assertIn("--strict-mcp-config", command)

    def test_allowed_tools_alone_does_not_restrict_the_tool_set(self) -> None:
        command = _cli_command(allowed_tools=[])

        self.assertNotIn("--tools", command)


if __name__ == "__main__":
    unittest.main()
