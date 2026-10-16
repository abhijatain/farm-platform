"""All demo data is deliberately fictional; only real workers create imagery."""
import json
from datetime import date
from pathlib import Path

import pytest

from app.cli.four_crop_demo_plan import (
    CROPS,activity_timestamp,plan_activities,satellite_date_windows,
    validate_demo_plan,
)
from app.cli.seed_four_crop_demo import load_field_polygon


def test_four_complete_non_overlapping_crop_histories():
    validate_demo_plan()
    assert [c.label for c in CROPS] == [
        "Wheat 2025","Rice 2025","Wheat 2026","Rice 2026",
    ]
    for crop in CROPS:
        events=plan_activities(crop)
        assert len(events)>=25
        assert events[0].occurred_on >= crop.started_on
        assert len([e for e in events if e.activity_type=="harvest"])==1
        assert all(e.satellite_metrics for e in events)
        assert all(e.occurred_on >= crop.started_on for e in events)
        assert not any(e.occurred_on >= crop.harvested_on and
          e.activity_type in ("pesticide","fungicide","irrigation") for e in events)
    assert satellite_date_windows() == [
        (c.started_on,c.harvested_on,c.label) for c in CROPS
    ]


def test_activity_time_keeps_indian_civil_date():
    stamp=activity_timestamp(date(2026,6,8))
    assert stamp.date()==date(2026,6,8)
    assert stamp.utcoffset().total_seconds()==19800


def test_field_geometry_accepts_single_multipolygon(tmp_path:Path):
    ring=[[77.05,29.91],[77.06,29.91],[77.06,29.92],
          [77.05,29.92],[77.05,29.91]]
    path=tmp_path/"one-field.geojson"
    path.write_text(json.dumps({
        "type":"FeatureCollection",
        "features":[{"type":"Feature","geometry":{
            "type":"MultiPolygon","coordinates":[[[ring]]]
        },"properties":{"field_name":"demo"}}]
    }),encoding="utf-8")
    poly=load_field_polygon(path)
    assert poly.geom_type=="Polygon" and poly.is_valid
    assert len(poly.exterior.coords)==5


def test_seeding_refuses_many_fields(tmp_path:Path):
    ring=[[77.05,29.91],[77.06,29.91],[77.06,29.92],
          [77.05,29.91]]
    path=tmp_path/"two-fields.geojson"
    path.write_text(json.dumps({"type":"FeatureCollection","features":[
        {"type":"Feature","geometry":{"type":"Polygon","coordinates":[ring]}},
        {"type":"Feature","geometry":{"type":"Polygon","coordinates":[ring]}},
    ]}),encoding="utf-8")
    with pytest.raises(ValueError,match="exactly one field"):
        load_field_polygon(path)


def test_no_fake_satellite_metric_values_in_plan():
    all_events=[item for crop in CROPS for item in plan_activities(crop)]
    assert all(isinstance(item.satellite_metrics,tuple) for item in all_events)
    assert all(item.notes and item.activity_type for item in all_events)
    assert {"ndvi","ndmi","ndre","bsi","sar_rvi","lst_c"} <= {
        metric for event in all_events for metric in event.satellite_metrics
    }
