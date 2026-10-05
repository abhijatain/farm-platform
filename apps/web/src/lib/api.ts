import {
  auth,
} from "./firebase";

import type {
  Activity,
  CropCycle,
  CurrentUser,
  Farm,
  Field,
  PolygonGeometry,
  Season,
  TimelineItem,
} from "../types/api";


const API_URL =
  import.meta.env
    .VITE_API_URL;


if (!API_URL) {
  throw new Error(
    "VITE_API_URL is missing.",
  );
}


async function apiFetch<T>(
  path: string,

  options:
    RequestInit = {},
): Promise<T> {

  const firebaseUser =
    auth.currentUser;


  if (!firebaseUser) {
    throw new Error(
      "Not authenticated.",
    );
  }


  const token =
    await firebaseUser
      .getIdToken();


  const headers =
    new Headers(
      options.headers,
    );


  headers.set(
    "Authorization",
    `Bearer ${token}`,
  );


  if (
    options.body &&
    !headers.has(
      "Content-Type",
    )
  ) {
    headers.set(
      "Content-Type",
      "application/json",
    );
  }


  const response =
    await fetch(
      `${API_URL}${path}`,
      {
        ...options,
        headers,
      },
    );


  if (!response.ok) {

    let message =
      `Request failed (${response.status})`;


    try {

      const body =
        await response.json();


      if (body.detail) {

        message =
          typeof body.detail
            === "string"
            ? body.detail
            : JSON.stringify(
                body.detail,
              );

      }

    } catch {
      // Keep fallback.
    }


    throw new Error(
      message,
    );
  }


  if (
    response.status === 204
  ) {
    return undefined as T;
  }


  return response.json() as Promise<T>;
}



/* AUTH */

export function getMe() {
  return apiFetch<
    CurrentUser
  >(
    "/auth/me",
  );
}



/* FARMS */

export function listFarms() {

  return apiFetch<
    Farm[]
  >(
    "/farms",
  );

}


export function createFarm(
  data: {
    name: string;
    location_name:
      string | null;
  },
) {

  return apiFetch<Farm>(
    "/farms",
    {
      method: "POST",

      body:
        JSON.stringify(
          data,
        ),
    },
  );

}



/* FIELDS */

export function listFields(
  farmId: string,
) {

  return apiFetch<
    Field[]
  >(
    `/farms/${farmId}/fields`,
  );

}


export function createField(
  farmId: string,

  data: {
    name: string;

    boundary:
      PolygonGeometry;
  },
) {

  return apiFetch<Field>(
    `/farms/${farmId}/fields`,

    {
      method: "POST",

      body:
        JSON.stringify(
          data,
        ),
    },
  );

}



/* SEASONS */

export function listSeasons(
  farmId: string,
) {

  return apiFetch<
    Season[]
  >(
    `/farms/${farmId}/seasons`,
  );

}


export function createSeason(
  farmId: string,

  data: {
    name: string;

    season_type:
      string | null;

    started_on: string;

    ended_on:
      string | null;
  },
) {

  return apiFetch<Season>(
    `/farms/${farmId}/seasons`,

    {
      method: "POST",

      body:
        JSON.stringify(
          data,
        ),
    },
  );

}



/* CROP CYCLES */

export function listFieldCropCycles(
  fieldId: string,
) {

  return apiFetch<
    CropCycle[]
  >(
    `/fields/${fieldId}/crop-cycles`,
  );

}
export function listSeasonCropCycles(
  seasonId: string,
) {
  return apiFetch<CropCycle[]>(
    `/seasons/${seasonId}/crop-cycles`,
  );
}


export function createCropCycle(
  seasonId: string,

  data: {
    field_id: string;

    crop_name: string;

    variety:
      string | null;

    started_on: string;

    planted_on:
      string | null;

    expected_harvest_on:
      string | null;

    harvested_on:
      string | null;

    notes:
      string | null;
  },
) {

  return apiFetch<
    CropCycle
  >(
    `/seasons/${seasonId}/crop-cycles`,

    {
      method: "POST",

      body:
        JSON.stringify(
          data,
        ),
    },
  );

}



/* ACTIVITIES */

export function createActivity(
  fieldId: string,

  data: {
    crop_cycle_id:
      string | null;

    activity_type:
      string;

    occurred_at:
      string;

    notes:
      string | null;

    details:
      Record<
        string,
        unknown
      >;
  },
) {

  return apiFetch<
    Activity
  >(
    `/fields/${fieldId}/activities`,

    {
      method: "POST",

      body:
        JSON.stringify(
          data,
        ),
    },
  );

}



/* TIMELINE */

export function getFieldTimeline(
  fieldId: string,
) {

  return apiFetch<
    TimelineItem[]
  >(
    `/fields/${fieldId}/timeline`,
  );

}
