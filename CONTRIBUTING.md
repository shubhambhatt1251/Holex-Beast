# Contributing to Holex Beast

Thanks for your interest! Here's how to get started.

## Setup

```bash
git clone https://github.com/shubhambhatt1251/Holex-Beast.git
cd Holex-Beast
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
pip install ruff pytest pytest-asyncio
```

## Code Style

- Follow PEP 8 (enforced by **ruff**)
- Max line length: 100 characters
- Use type hints on all public functions
- Write docstrings for classes and non-trivial functions

```bash
ruff check core/ gui/ services/ tests/
```

## Running Tests

```bash
pytest tests/ -v
```

## Pull Request Checklist

1. All existing tests pass (`pytest tests/ -v`)
2. New code has tests where reasonable
3. `ruff check` passes with no errors
4. Commit messages are clear and descriptive

## Project Structure

| Directory   | Purpose                                  |
|-------------|------------------------------------------|
| `core/`     | Backend engine (LLM, agent, voice, RAG)  |
| `gui/`      | PyQt5 GUI widgets and styling            |
| `services/` | External integrations (Firebase, SQLite) |
| `tests/`    | pytest test suite                        |
| `plugins/`  | Plugin directory (auto-discovered)       |

## Adding a New Tool

1. Create `core/agent/tools/your_tool.py`
2. Extend `BaseTool` from `core.agent.tools.base`
3. Implement `name`, `description`, `parameters`, and `execute()`
4. Register it in `core/agent/agent.py` → `_register_default_tools()`
5. Add a test in `tests/`

## Adding a New LLM Provider

1. Create `core/llm/providers/your_provider.py`
2. Extend `BaseLLMProvider` from `core.llm.base`
3. Implement `initialize()`, `generate()`, `stream()`, `get_models()`
4. Register it in `core/llm/router.py` → `initialize()`
