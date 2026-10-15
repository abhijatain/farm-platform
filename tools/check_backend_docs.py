"""Enforce readable Python module headers throughout the backend repository.

Run from the repository root: python tools/check_backend_docs.py
Pure standard-library AST check; does not need DB access or application secrets.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = (
    "services/api/app",
    "services/api/scripts",
    "services/api/tests",
    "services/api/alembic/versions",
    "services/satellite-worker/src",
    "services/satellite-worker/tests",
    "services/tiler/src",
    "services/tiler/tests",
)
EXTRA_FILES = ("services/api/alembic/env.py",)


def python_files() -> list[Path]:
    """Return source and test Python files without generated caches."""
    result = [
        path
        for relative in DIRECTORIES
        for path in (ROOT / relative).rglob("*.py")
        if not any(part in {"__pycache__", ".venv", ".pytest_cache"} for part in path.parts)
    ]
    return sorted(set([*result, *(ROOT / relative for relative in EXTRA_FILES)]))


def check_headers() -> list[str]:
    """Explain missing module docstrings with file paths for CI output."""
    errors: list[str] = []
    for path in python_files():
        relative = path.relative_to(ROOT)
        try:
            module = ast.parse(path.read_text(encoding="utf-8"), filename=str(relative))
        except (SyntaxError, UnicodeError) as exc:
            errors.append(f"{relative}: invalid Python source: {exc}")
            continue
        docstring = ast.get_docstring(module)
        if not docstring or len(docstring.strip()) < 16:
            errors.append(f"{relative}: missing informative top-level module docstring")
    return errors


def main() -> int:
    """Run the module-header quality gate as a command."""
    errors = check_headers()
    for message in errors:
        print(message)
    if errors:
        print(f"Backend module documentation failed for {len(errors)} files.")
        return 1
    print(f"Backend module documentation verified for {len(python_files())} Python files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
