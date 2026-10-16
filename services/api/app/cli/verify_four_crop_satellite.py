"""Read-only audit of real satellite readings for every seeded crop cycle.

Run after starting the satellite worker and passing its remote STAC/GCS jobs.
No synthetic NDVI, NDRE, NDMI, BSI, RVI or LST values are accepted.
"""
from __future__ import annotations
import argparse
from collections import Counter
from uuid import UUID

from sqlalchemy import select

REQUIRED_METRICS=("ndvi","ndmi","ndre","bsi","sar_rvi","lst_c")


def check(field_id:UUID,minimum_valid_percent:float=80.0) -> int:
    from app.db.session import SessionLocal
    from app.models.crop_cycle import CropCycle
    from app.models.satellite_observation import SatelliteObservation
    from app.models.satellite_metric import SatelliteMetric
    from app.models.satellite_ingestion_job import SatelliteIngestionJob

    with SessionLocal() as db:
        cycles=list(db.scalars(select(CropCycle).where(
            CropCycle.field_id==field_id).order_by(CropCycle.started_on)).all())
        if len(cycles)!=4:
            raise RuntimeError("Expected four crop cycles for the selected field, found "+str(len(cycles)))
        jobs=list(db.scalars(select(SatelliteIngestionJob).where(
            SatelliteIngestionJob.field_id==field_id)).all())
        print("Ingestion job states:",dict(Counter(j.status for j in jobs)))
        incomplete=False
        for cycle in cycles:
            rows=db.execute(
                select(SatelliteObservation.observed_on,SatelliteObservation.source,
                       SatelliteMetric.metric_type,SatelliteMetric.valid_pixel_percent)
                .join(SatelliteMetric,
                  SatelliteMetric.satellite_observation_id==SatelliteObservation.id)
                .where(
                    SatelliteObservation.field_id==field_id,
                    SatelliteObservation.observed_on>=cycle.started_on,
                    SatelliteObservation.observed_on<=cycle.harvested_on,
                    SatelliteMetric.metric_type.in_(REQUIRED_METRICS),
                )
            ).all()
            good=Counter((metric,source) for _d,source,metric,pct in rows
                         if pct is None or pct>=minimum_valid_percent)
            by_metric={metric:sum(n for (m,_),n in good.items() if m==metric)
                       for metric in REQUIRED_METRICS}
            missing=[metric for metric,count in by_metric.items() if count==0]
            if missing: incomplete=True
            print(f"{cycle.crop_name.upper()} {cycle.harvested_on.year}: {cycle.started_on}–{cycle.harvested_on}")
            print("  Real usable metric acquisitions:",by_metric)
            print("  Missing metrics:",missing or "none")
            print("  Radar RVI and LST are separate satellites, not substituted for NDVI.")
            if by_metric["ndvi"]<3:
                incomplete=True
                print("  WARNING: fewer than three usable NDVI dates to form a meaningful trend.")
        if incomplete:
            print("INCOMPLETE: real satellite coverage is missing; inspect job errors, cloud cover, GCS and provider access.")
            return 2
        print("PASS: all four crops have usable real images for the six core measurements.")
        return 0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--field-id",type=UUID,required=True)
    parser.add_argument("--minimum-valid-percent",type=float,default=80.0)
    args=parser.parse_args()
    if not 0<=args.minimum_valid_percent<=100:
        parser.error("coverage percent must be between 0 and 100")
    raise SystemExit(check(args.field_id,args.minimum_valid_percent))

if __name__=="__main__":
    main()
