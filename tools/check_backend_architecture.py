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




# Module names intentionally retired after migrating every in-repository caller.
RETIRED_MODULES = (
    *(f"app.services.{name}" for name in (
        "activity_satellite", "crop_phenology", "media_processing", "media_uploads",
        "radar_screening", "satellite_change", "satellite_ingestion",
        "satellite_timeline", "satellite_trends",
    )),
    *(f"satellite_worker.{name}" for name in (
        "anomaly", "anomaly_rules", "backfill_metric_anomalies", "db",
        "gcs_client", "ingestion_worker", "multisource_raster",
        "process_all_fields", "process_field", "process_landsat_field",
        "process_sentinel1_field", "raster_storage", "refresh_storage_manifests",
        "sentinel2", "stac", "storage_context", "storage_layout",
        "storage_manifests",
    )),
    "farm_tiler.change",
    "farm_tiler.gcs_path",
)

SOURCE_ROOTS = (
    "services/api/app", "services/api/scripts", "services/api/tests",
    "services/satellite-worker/src", "services/satellite-worker/tests",
    "services/tiler/src", "services/tiler/tests",
)

PACKAGE_ROOTS = {
    "app": "services/api/app",
    "satellite_worker": "services/satellite-worker/src/satellite_worker",
    "farm_tiler": "services/tiler/src/farm_tiler",
}

def check_retired_modules() -> list[str]:
    """Reject dead compatibility files and imports to removed modules."""
    errors: list[str] = []
    for module in RETIRED_MODULES:
        prefix, *parts = module.split(".")
        root = ROOT / PACKAGE_ROOTS[prefix]
        stem = root.joinpath(*parts)
        for candidate in (stem.with_suffix(".py"), stem / "__init__.py"):
            if candidate.exists():
                errors.append(f"{candidate.relative_to(ROOT)}: obsolete compatibility module")

    for source in SOURCE_ROOTS:
        for path in (ROOT / source).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    names = [
                        node.module,
                        *(f"{node.module}.{alias.name}" for alias in node.names)
                    ] if node.module else []
                else:
                    continue
                for name in names:
                    if name and any(
                        name == old or name.startswith(old + ".")
                        for old in RETIRED_MODULES
                    ):
                        errors.append(
                            f"{path.relative_to(ROOT)}:{node.lineno}: "
                            f"retired module import {name}"
                        )
    return errors

def main() -> int:
    """Run layering checks without importing a database or cloud client."""
    errors = check_boundaries() + check_retired_modules()
    for error in errors:
        print(error)
    if errors:
        print(f"Backend dependency boundary check failed: {len(errors)} violation(s).")
        return 1
    print("Backend dependency boundaries verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
