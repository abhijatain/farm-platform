from __future__ import annotations

import argparse
import subprocess
import sys

from sqlalchemy import text

from satellite_worker.db import (
    engine,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=("Run Sentinel-2 processing " "for every field.")
    )

    parser.add_argument(
        "--start",
        required=True,
    )

    parser.add_argument(
        "--end",
        required=True,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=20,
    )

    parser.add_argument(
        "--max-scene-cloud",
        type=float,
        default=60.0,
    )

    args = parser.parse_args()

    with engine.connect() as connection:

        rows = (
            connection.execute(
                text(
                    """
                SELECT
                    id,
                    name
                FROM fields
                ORDER BY name
                """
                )
            )
            .mappings()
            .all()
        )

    if not rows:
        print("No fields found.")

        return

    print(f"Found {len(rows)} fields.")

    successful = []
    failed = []

    for index, row in enumerate(
        rows,
        start=1,
    ):

        field_id = str(row["id"])

        field_name = row["name"]

        print()
        print("========================================")

        print(f"[{index}/{len(rows)}] " f"{field_name}")

        print(f"Field ID: {field_id}")

        print("========================================")

        command = [
            sys.executable,
            "-m",
            "satellite_worker.process_field",
            "--field-id",
            field_id,
            "--start",
            args.start,
            "--end",
            args.end,
            "--limit",
            str(args.limit),
            "--max-scene-cloud",
            str(args.max_scene_cloud),
        ]

        result = subprocess.run(
            command,
            check=False,
        )

        if result.returncode == 0:
            successful.append(field_name)

        else:
            failed.append(field_name)

    print()
    print("========================================")

    print("BATCH COMPLETE")

    print("========================================")

    print()
    print(f"Successful: " f"{len(successful)}")

    for field_name in successful:
        print(f"  ✓ {field_name}")

    if failed:

        print()
        print(f"Failed: " f"{len(failed)}")

        for field_name in failed:
            print(f"  ✗ {field_name}")


if __name__ == "__main__":
    main()
