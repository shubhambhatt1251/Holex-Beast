"""
Runs user code in a subprocess with a timeout.

This is NOT a proper sandbox - for a real app you'd want Docker
or something. But it's good enough for a desktop assistant where
the user is running their own code anyway.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import textwrap
from pathlib import Path

from core.agent.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 15

# Aggressive string-level filter — reject before even spawning a process.
_BLOCKED_TOKENS = (
    "import os", "import sys", "import subprocess", "import shutil",
    "import socket", "import ctypes", "import signal",
    "__import__", "importlib",
    "os.system", "os.popen", "os.exec",
    "subprocess.", "shutil.rmtree",
    "open(", "pathlib",
    "exec(", "eval(",
)


class CodeRunnerTool(BaseTool):
    """Execute Python snippets in a sandboxed subprocess."""

    @property
    def name(self) -> str:
        return "code_runner"

    @property
    def description(self) -> str:
        return (
            "Execute Python code and return its stdout output.  Good for "
            "calculations, data processing, text manipulation, or anything "
            "that benefits from running real code.  Runs in an isolated "
            "subprocess with a timeout."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute",
                },
            },
            "required": ["code"],
        }

    async def execute(self, code: str, **kwargs) -> ToolResult:
        lowered = code.lower()
        for token in _BLOCKED_TOKENS:
            if token.lower() in lowered:
                return ToolResult(
                    success=False, output="",
                    error=f"Blocked — forbidden operation: {token}",
                )

        # Wrap so the subprocess has access to safe stdlib modules
        wrapper = textwrap.dedent(f"""\
import math, json, datetime, re, collections, itertools, functools, statistics, random, textwrap, string
{textwrap.dedent(code)}
""")

        try:
            result = subprocess.run(
                [sys.executable, "-c", wrapper],
                capture_output=True,
                text=True,
                timeout=_TIMEOUT_SECONDS,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                cwd=str(Path.cwd()),
            )

            stdout = result.stdout.strip()
            stderr = result.stderr.strip()

            if result.returncode != 0:
                err_lines = stderr.splitlines()[-20:]
                return ToolResult(
                    success=False, output="",
                    error=f"Exit code {result.returncode}\n```\n" + "\n".join(err_lines) + "\n```",
                )

            output = stdout or "Code executed successfully (no output)."
            if stderr:
                output += f"\n\nstderr:\n{stderr}"

            return ToolResult(
                success=True,
                output=f"```\n{output}\n```",
                data={"stdout": stdout, "stderr": stderr},
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False, output="",
                error=f"Timed out after {_TIMEOUT_SECONDS}s.",
            )
        except Exception as exc:
            logger.error("code_runner subprocess error: %s", exc)
            return ToolResult(success=False, output="", error=str(exc))
