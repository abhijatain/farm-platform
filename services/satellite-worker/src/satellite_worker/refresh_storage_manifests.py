"""Legacy entry point for satellite_worker.cli.refresh_storage_manifests.

Keep this module for existing CLI invocations and integration imports; the
implementation belongs in the organized sensor, ingestion or CLI package.
"""

from satellite_worker.cli.refresh_storage_manifests import *  # noqa: F403

if __name__ == "__main__":
    main()
