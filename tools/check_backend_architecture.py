"""Verify that domain, storage, and processing packages remain decoupled.

Use Python's AST rather than external tooling to keep this check available
on every developer machine and in the existing GitHub Actions workflow.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# A lower layer must never reach upward to an HTTP router or sensor pipeline.
RULES = (
    ("services/api/app/domains", ("app.api.routes", "app.api.deps")),
    ("services/satellite-worker/src/satellite_worker/persistence", ("satellite_worker.sources", "satellite_worker.ingestion", "satellite_worker.cli")),
    ("services/satellite-worker/src/satellite_worker/storage", ("satellite_worker.ingestion", "satellite_worker.cli")),
    ("services/satellite-worker/src/satellite_worker/processing", ("satellite_worker.ingestion", "satellite_worker.cli", "satellite_worker.storage")),
    ("services/tiler/src/farm_tiler/services", ("farm_tiler.main",)),
    ("services/tiler/src/farm_tiler/storage", ("farm_tiler.main", "farm_tiler.services")),
)


def imported_modules(module: ast.AST) -> list[tuple[int, str]]:
    """Collect imports, retaining source line numbers for developer feedback."""
    imports: list[tuple[int, str]] = []
    for node in ast.walk(module):
        if isinstance(node, ast.Import):
            imports.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append((node.lineno, node.module))
    return imports


def check_boundaries() -> list[str]:
    """Describe any import dependency flowing against the intended layers."""
    errors: list[str] = []
    for folder, forbidden in RULES:
        for path in (ROOT / folder).rglob("*.py"):
            relative = path.relative_to(ROOT)
            module = ast.parse(path.read_text(encoding="utf-8"), filename=str(relative))
            for line, imported in imported_modules(module):
                if any(
                    imported == prefix or imported.startswith(prefix + ".")
                    for prefix in forbidden
                ):
                    errors.append(f"{relative}:{line}: forbidden dependency: {imported}")
    return errors


def main() -> int:
    """Run layering checks without importing a database or cloud client."""
    errors = check_boundaries()
    for error in errors:
        print(error)
    if errors:
        print(f"Backend dependency boundary check failed: {len(errors)} violation(s).")
        return 1
    print("Backend dependency boundaries verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
