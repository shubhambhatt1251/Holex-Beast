"""Tests for the system prompt and agent tool security boundaries."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# System Prompt

def test_system_prompt_contains_date():
    """System prompt should include the current UTC date/time."""
    from core.agent.prompts import get_system_prompt

    prompt = get_system_prompt()
    assert "Current date/time (UTC):" in prompt


def test_system_prompt_mentions_capabilities():
    """System prompt should list all major capabilities."""
    from core.agent.prompts import get_system_prompt

    prompt = get_system_prompt()
    assert "Web search" in prompt
    assert "calculator" in prompt.lower() or "calculation" in prompt.lower()
    assert "weather" in prompt.lower()
    assert "Wikipedia" in prompt
    assert "code execution" in prompt.lower() or "code_runner" in prompt.lower() or "Python code" in prompt


def test_system_prompt_returns_string():
    """get_system_prompt should always return a non-empty string."""
    from core.agent.prompts import get_system_prompt

    prompt = get_system_prompt()
    assert isinstance(prompt, str)
    assert len(prompt) > 200  # substantial prompt


def test_rag_context_prompt_exists():
    """RAG context prompt template should be importable and contain placeholder."""
    from core.agent.prompts import RAG_CONTEXT_PROMPT

    assert isinstance(RAG_CONTEXT_PROMPT, str)
    assert "{context}" in RAG_CONTEXT_PROMPT or "context" in RAG_CONTEXT_PROMPT.lower()


# Code Runner Security

def test_code_runner_blocks_os_import():
    """Code runner should reject code that imports os."""
    import asyncio

    from core.agent.tools.code_runner import CodeRunnerTool

    runner = CodeRunnerTool()
    result = asyncio.run(runner.execute(code="import os; os.listdir('.')"))
    assert not result.success


def test_code_runner_blocks_file_access():
    """Code runner should reject code that opens files."""
    import asyncio

    from core.agent.tools.code_runner import CodeRunnerTool

    runner = CodeRunnerTool()
    result = asyncio.run(runner.execute(code="open('/etc/passwd').read()"))
    assert not result.success


def test_code_runner_blocks_eval():
    """Code runner should reject eval() calls."""
    import asyncio

    from core.agent.tools.code_runner import CodeRunnerTool

    runner = CodeRunnerTool()
    result = asyncio.run(runner.execute(code="eval('1+1')"))
    assert not result.success


def test_code_runner_allows_safe_math():
    """Code runner should allow safe math operations."""
    import asyncio

    from core.agent.tools.code_runner import CodeRunnerTool

    runner = CodeRunnerTool()
    result = asyncio.run(runner.execute(code="import math; print(math.factorial(10))"))
    assert result.success
    assert "3628800" in result.output


def test_code_runner_timeout_enforcement():
    """Code runner should timeout on infinite loops."""
    import asyncio

    from core.agent.tools.code_runner import CodeRunnerTool

    runner = CodeRunnerTool()
    result = asyncio.run(runner.execute(code="while True: pass"))
    assert not result.success
    # Timeout message may be in .output or .error depending on implementation
    combined = (result.output + " " + (result.error or "")).lower()
    assert "timeout" in combined or "timed out" in combined


# Calculator Security

def test_calculator_blocks_import_in_expression():
    """Calculator should reject expressions with import."""
    import asyncio

    from core.agent.tools.calculator import CalculatorTool

    calc = CalculatorTool()
    result = asyncio.run(calc.execute(expression="__import__('os')"))
    assert not result.success


def test_calculator_supports_trig():
    """Calculator should handle trigonometric functions."""
    import asyncio

    from core.agent.tools.calculator import CalculatorTool

    calc = CalculatorTool()
    result = asyncio.run(calc.execute(expression="sin(pi/2)"))
    assert result.success
    assert "1" in result.output


def test_calculator_supports_logarithms():
    """Calculator should handle logarithmic functions."""
    import asyncio

    from core.agent.tools.calculator import CalculatorTool

    calc = CalculatorTool()
    result = asyncio.run(calc.execute(expression="log10(1000)"))
    assert result.success
    assert "3" in result.output
