# AGENTS.md

## About this project

Auto Forex is a full-stack web application for managing algorithmic forex trading operations across
multiple OANDA accounts with real-time market data streaming, strategy execution, position tracking,
and risk management.

## Dev environment tips

- This project uses `uv` to set up the Python environment.
- Python executable is installed in the `${workspaceFolder}/.venv/bin` directory.
- Use `uv sync` to install dependencies synced with pyproject.toml.
- Use `uv pip install` to install additional libraries.
- Use `uv run ruff check .` and `uv run ty check .` for linting, formatting, and type checking.

## Project Structure

Key directories and files:

```

```

## Design instructions

- Always consider testability, readability, and disposability.
- Always consider separation of concerns so that each module, class, and function has a clear boundary.
- Use Enum instead of str, and create objects rather than using multiple primitive variables.

## Coding instructions

- Do not hesitate to restructure the existing code.
- Do not create duplicate models, logic, or functions.
- Always use type hint for attributes and variables and returns.
- Always consider splitting files if the file is longer than 500 lines.

## Testing instructions

- Use `uv run pytest` to execute tests.
- Create unit tests under the `${workspaceFolder}/tests/unit` directory.
- Create integration tests under the `${workspaceFolder}/tests/integration` directory.
- Create end-to-end tests under the `${workspaceFolder}/tests/e2e` directory.
- Always create a unit test for a new module. The module name must start with "test\_".

## PR instructions

- Always run `uv run pytest`, `uv run ruff check .`, and `uv run ty check .` before committing changes.
- Always create a new branch for pull requests.
