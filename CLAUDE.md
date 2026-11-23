# Project rules (always follow)

## Every reply
- Start every reply with "Srinivasa," as the first word.

## Installations: always use uv (never pip)
- Use uv for everything: creating the environment, adding packages, running code.
- If the project is not set up yet: run `uv init` in the project root (creates pyproject.toml).
- Add packages with `uv add <package>` (this installs into the project's .venv and records the version in pyproject.toml and uv.lock).
- Remove packages with `uv remove <package>`.
- Run code and tests with `uv run <command>` (for example `uv run streamlit run app.py`, `uv run pytest`), so they always use the project's .venv.
- Never use `pip install` and never install anything globally.
- Commit pyproject.toml and uv.lock. Keep .venv in .gitignore.
- Before deployment, also create requirements.txt from uv: `uv export --format requirements-txt --no-hashes > requirements.txt`

## Explaining things to me: first principles + simple words
Whenever you explain a concept, a design choice, an error, or ask me to decide something:
1. Start from first principles: what is the basic problem, and why does it exist?
2. Build up step by step to the answer. Don't skip steps.
3. Use simple, everyday words. Explain any technical term the first time you use it.
4. Give a small concrete example where it helps.
5. For decisions: list the options, the trade-offs of each in plain words, and your recommendation with the reason. Then wait for my choice.
6. Keep it clear and short. No jargon dumps.

## Git
- Small, clear commits.
- Never add any Claude co-author or attribution lines to commit messages.