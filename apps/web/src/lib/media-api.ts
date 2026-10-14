import { apiRequest } from "./api-client";

import type {
  MediaAsset,
  MediaUploadTarget,
} from "../types/media";


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
  return apiRequest<MediaUploadTarget>(
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
  return apiRequest<MediaAsset>(
    `/media/${mediaId}/complete`,
    {
      method: "POST",
    },
  );
}


export function retryMediaProcessing(
  mediaId: string,
) {
  return apiRequest<MediaAsset>(
    `/media/${mediaId}/process`,
    {
      method: "POST",
    },
  );
}


export function listFieldMedia(
  fieldId: string,
) {
  return apiRequest<MediaAsset[]>(
    `/fields/${fieldId}/media`,
  );
}


export function deleteMediaAsset(
  mediaId: string,
) {
  return apiRequest<void>(
    `/media/${mediaId}`,
    {
      method: "DELETE",
    },
  );
}
