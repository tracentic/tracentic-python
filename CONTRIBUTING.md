# Contributing

Thanks for your interest in improving the Tracentic Python SDK. This guide covers how to get set up, the conventions we follow, and how to land a change.

## Getting started

Prerequisites:

- Python 3.10 or newer
- git

Clone and set up a virtual environment:

```bash
git clone https://github.com/tracentic/tracentic-python
cd tracentic-python
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,starlette]"
pytest
```

## Reporting bugs & requesting features

Open an issue on GitHub. For bugs, include:

- SDK version
- Python version and OS
- Minimal reproduction
- What you expected vs. what happened

For features, describe the use case first - the shape of the API usually follows from the problem.

## Making a change

1. Fork and create a branch off `main`.
2. Keep the change focused - one logical change per PR.
3. Add or update tests under `tests/`. New public behavior needs a test.
4. Run the full suite: `pytest`.
5. Lint and type-check: `ruff check .` and `mypy src`.
6. Update `CHANGELOG.md` under `[Unreleased]` if the change is user-visible.
7. Update `README.md` if you add or change a public API surface.
8. Open a PR with a short description of **what** and **why** - the diff shows the how.

## Code style

- Follow existing conventions in the file you're editing.
- Type hints are required on public APIs; `mypy --strict` is enforced.
- Keep modules prefixed with `_` internal; the public surface lives in `tracentic/__init__.py`.
- Don't add comments that restate what the code does. Comments should explain non-obvious **why**.

## Public API stability

Until we ship 1.0, minor versions may include breaking changes, but we try to avoid them. If your PR changes a public signature, call it out in the description.

## License & contributor agreement

By submitting a contribution, you agree that it is licensed under the Apache License 2.0 (see [LICENSE](LICENSE)), consistent with section 5 of the license.
