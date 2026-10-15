"""Shared worker connection pool across satellite persistence modules."""

from sqlalchemy import create_engine

from satellite_worker.config import settings

# One engine avoids separate connection pools for scene and job repositories.
engine = create_engine(settings.database_url)
