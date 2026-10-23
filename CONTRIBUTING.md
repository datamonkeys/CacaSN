# Contributing

Thanks for helping. Issues and pull requests are welcome in English or Portuguese.

## Setup

    uv sync --all-extras          # Python 3.9+; installs the locked dependencies and dev tools

No uv? `pip install -e ".[sentry,experimentos]" ruff mypy` works too.

## Before opening a PR

    uv run python -m unittest discover -s tests -t .   # offline: every API is mocked
    uv run ruff check . && uv run ruff format --check .
    uv run mypy

CI runs the same commands on Python 3.9 and 3.12, plus `pip-audit` and a Docker build.

## Ground rules

- **Never hit the real APIs in tests.** Mock `get_json`, `vizier` and `tns_busca` (see `tests/ajuda.py`).
- **Changing the score?** Say how you measured it. The current weights were chosen against what
  professional teams reported to TNS (README, "Score"); a change should show it doesn't lower that AUC.
- **Be polite to the services.** Keep the TNS limiter (10 cone searches/min) and the retry backoff.
- Never commit `tns.json`, `.env` or API keys.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`…).
- Note user-visible changes in `CHANGELOG.md`.
