# Repo Guidelines

This project implements a multi-agent market analysis system using LangGraph and FastAPI. Follow these conventions when contributing.

## Environment Setup
- Python 3.10+ is required.
- Dependency management is done with **uv**. Install it via `pip install uv` or the official installer script.
- Install dependencies with `uv sync` and run the project using `uv run main.py`.
- Alternatively you can create a virtual environment and `pip install -r requirements.txt`.

## Code Style
- Run `ruff` for linting and formatting before committing. Using `uvx` is recommended:
  ```bash
  uvx ruff check --fix
  uvx ruff format
  ```
- The configuration in `ruff.toml` enforces 4 space indentation, double quotes, and 88 character lines.

## Testing
- Tests live under `tests/` and use `pytest`. Execute them with:
  ```bash
  pytest
  ```
  Some tests require API keys (.env) and may skip if keys are missing.

## Adding Agents
- New agent nodes should subclass `Node` in `src/graph/nodes/`.
- Implement `_run` and optionally `_invoke` for API access. Register the node in `main.py` using `graph_builder.add_node()`.
- When merged into the main branch, pipelines under `pipelines/` are automatically discovered and integrated with OpenWebUI.

## Running the API Server
- The FastAPI server listens on port **8000** by default. API docs are available at `/docs`.

