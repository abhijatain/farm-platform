export type CurrentUser = {
  id: string;
  phone_e164: string;
  name: string | null;
  preferred_language: string;

  created_at: string;
  updated_at: string;
};


export type Farm = {
  id: string;

  name: string;
  location_name: string | null;

  created_at: string;
  updated_at: string;
};


export type PolygonGeometry = {
  type: "Polygon";
  coordinates: number[][][];
};


export type Field = {
  id: string;
  farm_id: string;

  name: string;

  boundary: PolygonGeometry;

  area_square_metres: number;
  area_hectares: number;
  area_acres: number;

  created_at: string;
  updated_at: string;
};


export type Season = {
  id: string;
  farm_id: string;

  name: string;
  season_type: string | null;
  status: string;

  started_on: string;
  ended_on: string | null;

  created_at: string;
  updated_at: string;
};


export type CropCycle = {
  id: string;

  season_id: string;
  field_id: string;

  crop_name: string;
  variety: string | null;

  status: string;

  started_on: string;
  planted_on: string | null;

  expected_harvest_on: string | null;
  harvested_on: string | null;

  notes: string | null;

  created_at: string;
  updated_at: string;
};


export type Activity = {
  id: string;

  field_id: string;
  crop_cycle_id: string | null;

  activity_type: string;
  occurred_at: string;

  notes: string | null;

  details: Record<
    string,
    unknown
  >;

  created_at: string;
  updated_at: string;
};


export type TimelineItem = {
  type: "activity";

  id: string;

  occurred_at: string;

  activity_type: string;

  notes: string | null;

  details: Record<
    string,
    unknown
  >;

  crop_cycle_id: string | null;

  crop_name: string | null;
  variety: string | null;

  season_id: string | null;
  season_name: string | null;
};
