import { auth } from "./firebase";

import type {
  MediaAsset,
  MediaUploadTarget,
} from "../types/media";


const API_URL =
  import.meta.env.VITE_API_URL;


if (!API_URL) {
  throw new Error(
    "VITE_API_URL is missing.",
  );
}


async function authHeaders(
  initial?: HeadersInit,
) {
  const user =
    auth.currentUser;

  if (!user) {
    throw new Error(
      "Not authenticated.",
    );
  }

  const token =
    await user.getIdToken();

  const headers =
    new Headers(initial);

  headers.set(
    "Authorization",
    `Bearer ${token}`,
  );

  return headers;
}


async function requestJson<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers =
    await authHeaders(
      options.headers,
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

  const response = await fetch(
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
          typeof body.detail ===
          "string"
            ? body.detail
            : JSON.stringify(
                body.detail,
              );
      }
    } catch {
      // Use fallback.
    }

    throw new Error(message);
  }

  if (
    response.status === 204
  ) {
    return undefined as T;
  }

  return (
    response.json() as Promise<T>
  );
}


export function createMediaUpload(
  fieldId: string,
  data: {
    original_filename: string;
    content_type: string;
    size_bytes: number;
    activity_id: string | null;
    crop_cycle_id: string | null;
    captured_at: string | null;
    caption: string | null;
  },
) {
  return requestJson<MediaUploadTarget>(
    `/fields/${fieldId}/media/uploads`,
    {
      method: "POST",
      body: JSON.stringify(data),
    },
  );
}


export async function uploadMediaFile(
  target: MediaUploadTarget,
  file: File,
) {
  const response = await fetch(
    target.upload_url,
    {
      method: "PUT",
      headers:
        target.upload_headers,
      body: file,
    },
  );

  if (!response.ok) {
    throw new Error(
      `Cloud upload failed (${response.status})`,
    );
  }
}


export function completeMediaUpload(
  mediaId: string,
) {
  return requestJson<MediaAsset>(
    `/media/${mediaId}/complete`,
    {
      method: "POST",
    },
  );
}


export function retryMediaProcessing(
  mediaId: string,
) {
  return requestJson<MediaAsset>(
    `/media/${mediaId}/process`,
    {
      method: "POST",
    },
  );
}


export function listFieldMedia(
  fieldId: string,
) {
  return requestJson<MediaAsset[]>(
    `/fields/${fieldId}/media`,
  );
}


export function deleteMediaAsset(
  mediaId: string,
) {
  return requestJson<void>(
    `/media/${mediaId}`,
    {
      method: "DELETE",
    },
  );
}
