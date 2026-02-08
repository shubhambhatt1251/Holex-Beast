"""Math evaluator with a restricted namespace so users can't do anything sketchy."""

from __future__ import annotations

import logging
import math

from core.agent.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

# Safe math namespace (no builtins, no imports)
SAFE_MATH_GLOBALS = {
    "__builtins__": {},
    "abs": abs, "round": round, "min": min, "max": max, "sum": sum,
    "int": int, "float": float, "pow": pow, "len": len,
    # Math module
    "pi": math.pi, "e": math.e, "tau": math.tau, "inf": math.inf,
    "sqrt": math.sqrt, "cbrt": lambda x: x ** (1/3),
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
    "log": math.log, "log2": math.log2, "log10": math.log10,
    "exp": math.exp, "factorial": math.factorial,
    "ceil": math.ceil, "floor": math.floor,
    "gcd": math.gcd, "degrees": math.degrees, "radians": math.radians,
}


class CalculatorTool(BaseTool):
    """Evaluate mathematical expressions safely."""

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return (
            "Evaluate mathematical expressions. Supports arithmetic (+, -, *, /, **, %), "
            "trigonometry (sin, cos, tan), logarithms (log, log2, log10), "
            "constants (pi, e), and more. Use for ANY calculation."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Math expression to evaluate, e.g. 'sqrt(144) + 2**10'",
                },
            },
            "required": ["expression"],
        }

    async def execute(self, expression: str, **kwargs) -> ToolResult:
        try:
            # Security: compile to check for dangerous operations
            code = compile(expression, "<calc>", "eval")

            # Check for forbidden names
            forbidden = {"import", "exec", "eval", "open", "os", "sys", "__"}
            for name in code.co_names:
                if any(f in name.lower() for f in forbidden):
                    return ToolResult(
                        success=False, output="",
                        error=f"Forbidden operation: {name}",
                    )

            result = eval(code, SAFE_MATH_GLOBALS)

            # Format nicely
            if isinstance(result, float):
                if result == int(result) and abs(result) < 1e15:
                    formatted = f"{int(result):,}"
                else:
                    formatted = f"{result:,.6f}".rstrip("0").rstrip(".")
            elif isinstance(result, int):
                formatted = f"{result:,}"
            else:
                formatted = str(result)

            return ToolResult(
                success=True,
                output=f"`{expression}` = **{formatted}**",
                data={"expression": expression, "result": result},
            )

        except SyntaxError:
            return ToolResult(
                success=False, output="",
                error=f"Invalid expression: {expression}",
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
