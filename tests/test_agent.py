"""Tests for agent tools — calculator, code runner, and tool schema validation."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_calculator_basic():
    """Calculator tool should evaluate safe expressions."""
    import asyncio

    from core.agent.tools.calculator import CalculatorTool

    calc = CalculatorTool()
    result = asyncio.run(calc.execute(expression="2 + 3 * 4"))
    assert result.success
    assert "14" in result.output


def test_calculator_math_functions():
    """Calculator should support math functions."""
    import asyncio

    from core.agent.tools.calculator import CalculatorTool

    calc = CalculatorTool()
    result = asyncio.run(calc.execute(expression="sqrt(144)"))
    assert result.success
    assert "12" in result.output


def test_calculator_rejects_dangerous():
    """Calculator should reject dangerous expressions."""
    import asyncio

    from core.agent.tools.calculator import CalculatorTool

    calc = CalculatorTool()
    result = asyncio.run(
        calc.execute(expression="__import__('os').system('rm -rf /')")
    )
    assert not result.success


def test_tool_schema():
    """All tools should produce valid OpenAI tool schema."""
    from core.agent.tools.calculator import CalculatorTool
    from core.agent.tools.web_search import WebSearchTool
    from core.agent.tools.wikipedia_tool import WikipediaTool

    for ToolClass in [CalculatorTool, WebSearchTool, WikipediaTool]:
        tool = ToolClass()
        schema = tool.to_openai_tool()
        assert schema["type"] == "function"
        assert "function" in schema
        assert "name" in schema["function"]
        assert "description" in schema["function"]
        assert "parameters" in schema["function"]


def test_code_runner_basic():
    """Code runner should execute safe Python."""
    import asyncio

    from core.agent.tools.code_runner import CodeRunnerTool

    runner = CodeRunnerTool()
    result = asyncio.run(runner.execute(code="print(sum(range(10)))"))
    assert result.success
    assert "45" in result.output


def test_code_runner_rejects_imports():
    """Code runner should block dangerous imports."""
    import asyncio

    from core.agent.tools.code_runner import CodeRunnerTool

    runner = CodeRunnerTool()
    result = asyncio.run(
        runner.execute(code="import subprocess; subprocess.call(['ls'])")
    )
    assert not result.success
