
export type MediaType =
  | "image"
  | "video";

export type MediaStatus =
  | "pending"
  | "ready"
  | "failed";

export type MediaAsset = {
  id: string;

  uploaded_by_user_id: string;

  field_id: string;

  activity_id: string | null;

  crop_cycle_id: string | null;

  media_type: MediaType;

  status: MediaStatus;

  storage_backend: string;

  original_filename: string;

  content_type: string;

  size_bytes: number;

  captured_at: string | null;

  width: number | null;

  height: number | null;

  duration_seconds: number | null;

  caption: string | null;

  metadata_json: Record<string, unknown>;

  download_url: string | null;

  thumbnail_available: boolean;

  thumbnail_url: string | null;

  created_at: string;
  updated_at: string;
};

export type MediaUploadTarget = {
  media: MediaAsset;

  upload_method:
    | "api_put"
    | "gcs_signed_put";

  upload_url: string;

  upload_headers: Record<
    string,
    string
  >;
};
