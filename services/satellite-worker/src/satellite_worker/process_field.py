"""Legacy entry point for satellite_worker.sources.sentinel2.pipeline.

Keep this module for existing CLI invocations and integration imports; the
implementation belongs in the organized sensor, ingestion or CLI package.
"""

from satellite_worker.sources.sentinel2.pipeline import *  # noqa: F403

if __name__ == "__main__":
    main()
