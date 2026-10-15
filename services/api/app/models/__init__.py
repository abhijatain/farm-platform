"""Initialize the API models package and its stable imports."""

from app.models.activity import Activity
from app.models.crop_cycle import CropCycle
from app.models.crop_stage_observation import CropStageObservation
from app.models.farm import Farm
from app.models.field import Field
from app.models.media_asset import MediaAsset
from app.models.satellite_anomaly import SatelliteAnomaly
from app.models.satellite_ingestion_job import SatelliteIngestionJob
from app.models.satellite_metric import SatelliteMetric
from app.models.satellite_observation import SatelliteObservation
from app.models.season import Season
from app.models.user import User
from app.models.whatsapp_inbound_event import WhatsAppInboundEvent
from app.models.whatsapp_link import WhatsAppLink

__all__ = [
    "User",
    "Farm",
    "Field",
    "Season",
    "CropCycle",
    "CropStageObservation",
    "Activity",
    "SatelliteObservation",
    "SatelliteIngestionJob",
    "SatelliteAnomaly",
    "SatelliteMetric",
    "MediaAsset",
    "WhatsAppInboundEvent",
    "WhatsAppLink",
]
