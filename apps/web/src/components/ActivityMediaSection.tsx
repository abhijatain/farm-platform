
import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  Image as ImageIcon,
  Play,
  Trash2,
  Upload,
  Video,
  X,
} from "lucide-react";

import {
  completeMediaUpload,
  createMediaUpload,
  deleteMediaAsset,
  getMediaBlob,
  getMediaThumbnailBlob,
  listFieldMedia,
  retryMediaProcessing,
  uploadMediaFile,
} from "../lib/media-api";

import type {
  TimelineItem,
} from "../types/api";

import type {
  MediaAsset,
} from "../types/media";

import "./ActivityMediaSection.css";


type Props = {
  fieldId: string;

  activity: TimelineItem;
};


type MediaMode =
  | "activity"
  | "field";


type PendingMedia = {
  id: string;

  file: File;

  contentType: string;

  previewUrl: string;

  caption: string;
};


function contentTypeForFile(
  file: File,
) {
  if (file.type) {
    return file.type;
  }

  const name =
    file.name.toLowerCase();

  if (
    name.endsWith(".jpg") ||
    name.endsWith(".jpeg")
  ) {
    return "image/jpeg";
  }

  if (name.endsWith(".png")) {
    return "image/png";
  }

  if (name.endsWith(".webp")) {
    return "image/webp";
  }

  if (name.endsWith(".heic")) {
    return "image/heic";
  }

  if (name.endsWith(".heif")) {
    return "image/heif";
  }

  if (name.endsWith(".mp4")) {
    return "video/mp4";
  }

  if (name.endsWith(".mov")) {
    return "video/quicktime";
  }

  if (name.endsWith(".webm")) {
    return "video/webm";
  }

  return "";
}


function readableSize(
  sizeBytes: number,
) {
  const mb =
    sizeBytes /
    1024 /
    1024;

  if (mb >= 1) {
    return `${mb.toFixed(1)} MB`;
  }

  return `${(
    sizeBytes / 1024
  ).toFixed(0)} KB`;
}


function readableDuration(
  seconds: number | null,
) {
  if (
    seconds == null ||
    !Number.isFinite(seconds)
  ) {
    return null;
  }

  const total =
    Math.max(
      0,
      Math.round(seconds),
    );

  const minutes =
    Math.floor(
      total / 60
    );

  const remaining =
    total % 60;

  return (
    `${minutes}:` +
    `${remaining}`
      .padStart(
        2,
        "0",
      )
  );
}


function createPendingId(
  file: File,
  index: number,
) {
  return [
    file.name,
    file.lastModified,
    file.size,
    index,
    Date.now(),
  ].join("-");
}


function derivativeStatus(
  media: MediaAsset,
) {
  const value =
    media.metadata_json[
      "derivative_status"
    ];

  return (
    typeof value === "string"
      ? value
      : null
  );
}


export default function ActivityMediaSection({
  fieldId,
  activity,
}: Props) {
  const [
    mode,
    setMode,
  ] =
    useState<MediaMode>(
      "activity",
    );

  const [
    media,
    setMedia,
  ] =
    useState<MediaAsset[]>([]);

  const [
    pendingMedia,
    setPendingMedia,
  ] =
    useState<PendingMedia[]>([]);

  const [
    loading,
    setLoading,
  ] = useState(true);

  const [
    uploading,
    setUploading,
  ] = useState(false);

  const [
    error,
    setError,
  ] =
    useState<string | null>(
      null,
    );

  const inputRef =
    useRef<HTMLInputElement>(
      null,
    );


  async function loadMedia() {
    try {
      setLoading(true);

      const rows =
        await listFieldMedia(
          fieldId,
        );

      setMedia(rows);

    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to load media.",
      );

    } finally {
      setLoading(false);
    }
  }


  function clearPendingMedia() {
    setPendingMedia(
      (current) => {
        for (
          const item of current
        ) {
          URL.revokeObjectURL(
            item.previewUrl,
          );
        }

        return [];
      },
    );

    if (inputRef.current) {
      inputRef.current.value =
        "";
    }
  }


  useEffect(() => {
    setMode("activity");

    clearPendingMedia();

    void loadMedia();
  }, [
    fieldId,
    activity.id,
  ]);


  useEffect(() => {
    const waiting =
      media.some(
        (item) => {
          const status =
            derivativeStatus(
              item,
            );

          return (
            status === "queued" ||
            status === "processing"
          );
        },
      );

    if (!waiting) {
      return;
    }

    const timer =
      window.setTimeout(
        () => {
          void loadMedia();
        },
        1500,
      );

    return () => {
      window.clearTimeout(
        timer
      );
    };
  }, [media]);


  const visibleMedia =
    useMemo(
      () =>
        media.filter(
          (item) =>
            mode === "activity"
              ? item.activity_id ===
                activity.id
              : item.activity_id ===
                null,
        ),
      [
        media,
        mode,
        activity.id,
      ],
    );


  function stageFiles(
    files: FileList,
  ) {
    setError(null);

    const created:
      PendingMedia[] = [];

    try {
      Array.from(
        files,
      ).forEach(
        (
          file,
          index,
        ) => {
          const contentType =
            contentTypeForFile(
              file,
            );

          if (!contentType) {
            throw new Error(
              `Unsupported file type: ${file.name}`,
            );
          }

          created.push({
            id:
              createPendingId(
                file,
                index,
              ),
            file,
            contentType,
            previewUrl:
              URL.createObjectURL(
                file,
              ),
            caption: "",
          });
        },
      );

      setPendingMedia(
        (current) => [
          ...current,
          ...created,
        ],
      );

    } catch (stageError) {
      for (
        const item of created
      ) {
        URL.revokeObjectURL(
          item.previewUrl,
        );
      }

      setError(
        stageError instanceof Error
          ? stageError.message
          : "Unable to prepare selected media.",
      );
    }

    if (inputRef.current) {
      inputRef.current.value =
        "";
    }
  }


  function updatePendingCaption(
    mediaId: string,
    caption: string,
  ) {
    setPendingMedia(
      (current) =>
        current.map(
          (item) =>
            item.id === mediaId
              ? {
                  ...item,
                  caption,
                }
              : item,
        ),
    );
  }


  function removePendingMedia(
    mediaId: string,
  ) {
    setPendingMedia(
      (current) => {
        const item =
          current.find(
            (candidate) =>
              candidate.id ===
              mediaId,
          );

        if (item) {
          URL.revokeObjectURL(
            item.previewUrl,
          );
        }

        return current.filter(
          (candidate) =>
            candidate.id !==
            mediaId,
        );
      },
    );
  }


  async function uploadPendingMedia() {
    if (
      pendingMedia.length === 0
    ) {
      return;
    }

    setUploading(true);
    setError(null);

    try {
      for (
        const item of pendingMedia
      ) {
        const target =
          await createMediaUpload(
            fieldId,
            {
              original_filename:
                item.file.name,
              content_type:
                item.contentType,
              size_bytes:
                item.file.size,
              activity_id:
                mode ===
                "activity"
                  ? activity.id
                  : null,
              crop_cycle_id:
                activity.crop_cycle_id,
              captured_at:
                null,
              caption:
                item.caption.trim() ||
                null,
            },
          );

        await uploadMediaFile(
          target,
          item.file,
        );

        await completeMediaUpload(
          target.media.id,
        );
      }

      clearPendingMedia();

      await loadMedia();

    } catch (uploadError) {
      setError(
        uploadError instanceof Error
          ? uploadError.message
          : "Unable to upload media.",
      );

    } finally {
      setUploading(false);
    }
  }


  async function removeMedia(
    mediaId: string,
  ) {
    try {
      setError(null);

      await deleteMediaAsset(
        mediaId,
      );

      setMedia(
        (current) =>
          current.filter(
            (item) =>
              item.id !==
              mediaId,
          ),
      );

    } catch (deleteError) {
      setError(
        deleteError instanceof Error
          ? deleteError.message
          : "Unable to delete media.",
      );
    }
  }


  async function retryProcessing(
    mediaId: string,
  ) {
    try {
      setError(null);

      await retryMediaProcessing(
        mediaId,
      );

      await loadMedia();

    } catch (retryError) {
      setError(
        retryError instanceof Error
          ? retryError.message
          : "Unable to retry media processing.",
      );
    }
  }


  const hasPendingMedia =
    pendingMedia.length > 0;


  return (
    <section className="activity-media-section">
      <div className="activity-media-heading">
        <div>
          <span className="workspace-eyebrow">
            PHOTOS & VIDEOS
          </span>

          <h3>
            Field media
          </h3>

          <p>
            Upload media for this
            activity, or keep it linked
            only to the field. You can
            add a description to every
            photo or video.
          </p>
        </div>

        <button
          type="button"
          className="media-upload-button"
          disabled={uploading}
          onClick={() =>
            inputRef.current?.click()
          }
        >
          <Upload size={16} />

          Add media
        </button>

        <input
          ref={inputRef}
          className="media-file-input"
          type="file"
          accept="image/jpeg,image/png,image/webp,image/heic,image/heif,video/mp4,video/quicktime,video/webm"
          multiple
          onChange={(event) => {
            if (
              event.target.files &&
              event.target.files.length >
                0
            ) {
              stageFiles(
                event.target.files,
              );
            }
          }}
        />
      </div>

      <div className="media-mode-switch">
        <button
          type="button"
          className={
            mode === "activity"
              ? "active"
              : ""
          }
          disabled={
            uploading ||
            hasPendingMedia
          }
          onClick={() =>
            setMode("activity")
          }
        >
          This activity
        </button>

        <button
          type="button"
          className={
            mode === "field"
              ? "active"
              : ""
          }
          disabled={
            uploading ||
            hasPendingMedia
          }
          onClick={() =>
            setMode("field")
          }
        >
          Field only
        </button>
      </div>

      {hasPendingMedia && (
        <div className="media-upload-composer">
          <div className="media-upload-composer-header">
            <div>
              <span className="workspace-eyebrow">
                READY TO UPLOAD
              </span>

              <h4>
                Add descriptions
              </h4>

              <p>
                These files will be
                linked to{" "}
                <strong>
                  {mode ===
                  "activity"
                    ? "this activity"
                    : "the field only"}
                </strong>
                .
              </p>
            </div>

            <button
              type="button"
              className="media-composer-close"
              disabled={uploading}
              onClick={
                clearPendingMedia
              }
              aria-label="Cancel selected media"
            >
              <X size={18} />
            </button>
          </div>

          <div className="media-pending-list">
            {pendingMedia.map(
              (item) => (
                <PendingMediaEditor
                  key={item.id}
                  item={item}
                  disabled={
                    uploading
                  }
                  onCaptionChange={(
                    caption,
                  ) =>
                    updatePendingCaption(
                      item.id,
                      caption,
                    )
                  }
                  onRemove={() =>
                    removePendingMedia(
                      item.id,
                    )
                  }
                />
              ),
            )}
          </div>

          <div className="media-upload-actions">
            <button
              type="button"
              className="media-cancel-button"
              disabled={uploading}
              onClick={
                clearPendingMedia
              }
            >
              Cancel
            </button>

            <button
              type="button"
              className="media-confirm-upload-button"
              disabled={uploading}
              onClick={() =>
                void uploadPendingMedia()
              }
            >
              <Upload size={16} />

              {uploading
                ? "Uploading…"
                : `Upload ${
                    pendingMedia.length
                  } ${
                    pendingMedia.length ===
                    1
                      ? "file"
                      : "files"
                  }`}
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="media-error">
          {error}
        </div>
      )}

      {loading && (
        <p className="media-muted">
          Loading media…
        </p>
      )}

      {!loading &&
        visibleMedia.length === 0 &&
        !hasPendingMedia && (
          <div className="media-empty">
            <div>
              {mode ===
              "activity"
                ? (
                  <ImageIcon
                    size={22}
                  />
                )
                : (
                  <Video
                    size={22}
                  />
                )}
            </div>

            <strong>
              No media yet
            </strong>

            <span>
              {mode === "activity"
                ? "Uploads here will be linked to the selected activity."
                : "Uploads here stay linked to the field without an activity."}
            </span>
          </div>
        )}

      {!loading &&
        visibleMedia.length > 0 && (
          <div className="media-gallery">
            {visibleMedia.map(
              (item) => (
                <MediaCard
                  key={item.id}
                  media={item}
                  onDelete={() =>
                    void removeMedia(
                      item.id,
                    )
                  }
                  onRetry={() =>
                    void retryProcessing(
                      item.id,
                    )
                  }
                />
              ),
            )}
          </div>
        )}
    </section>
  );
}


function PendingMediaEditor({
  item,
  disabled,
  onCaptionChange,
  onRemove,
}: {
  item: PendingMedia;

  disabled: boolean;

  onCaptionChange: (
    caption: string,
  ) => void;

  onRemove: () => void;
}) {
  const isImage =
    item.contentType.startsWith(
      "image/",
    );

  const isVideo =
    item.contentType.startsWith(
      "video/",
    );

  return (
    <article className="media-pending-card">
      <div className="media-pending-preview">
        {isImage && (
          <img
            src={item.previewUrl}
            alt={item.file.name}
          />
        )}

        {isVideo && (
          <video
            src={item.previewUrl}
            controls
            preload="metadata"
          />
        )}

        {!isImage &&
          !isVideo && (
            <div className="media-preview-loading">
              Preview unavailable
            </div>
          )}
      </div>

      <div className="media-pending-content">
        <div className="media-pending-file-row">
          <div>
            <strong>
              {item.file.name}
            </strong>

            <span>
              {readableSize(
                item.file.size,
              )}
            </span>
          </div>

          <button
            type="button"
            className="media-delete-button"
            disabled={disabled}
            onClick={onRemove}
            aria-label={`Remove ${item.file.name}`}
          >
            <Trash2 size={15} />
          </button>
        </div>

        <label className="media-caption-field">
          <span>
            Description
          </span>

          <textarea
            value={item.caption}
            disabled={disabled}
            maxLength={1000}
            rows={3}
            placeholder="What do you notice here? For example: yellowing near the south-west corner after irrigation."
            onChange={(event) =>
              onCaptionChange(
                event.target.value,
              )
            }
          />

          <small>
            {item.caption.length}
            /1000
          </small>
        </label>
      </div>
    </article>
  );
}


function MediaCard({
  media,
  onDelete,
  onRetry,
}: {
  media: MediaAsset;

  onDelete: () => void;

  onRetry: () => void;
}) {
  const [
    originalLocalUrl,
    setOriginalLocalUrl,
  ] =
    useState<string | null>(
      null,
    );

  const [
    thumbnailLocalUrl,
    setThumbnailLocalUrl,
  ] =
    useState<string | null>(
      null,
    );

  const [
    previewError,
    setPreviewError,
  ] = useState(false);


  useEffect(() => {
    if (media.download_url) {
      setOriginalLocalUrl(
        null
      );

      return;
    }

    let cancelled = false;

    let objectUrl:
      | string
      | null = null;

    void getMediaBlob(
      media.id,
    )
      .then((blob) => {
        if (cancelled) {
          return;
        }

        objectUrl =
          URL.createObjectURL(
            blob,
          );

        setOriginalLocalUrl(
          objectUrl,
        );
      })
      .catch(() => {
        if (!cancelled) {
          setPreviewError(
            true,
          );
        }
      });

    return () => {
      cancelled = true;

      if (objectUrl) {
        URL.revokeObjectURL(
          objectUrl,
        );
      }
    };
  }, [
    media.id,
    media.download_url,
  ]);


  useEffect(() => {
    if (
      !media.thumbnail_available
      || media.thumbnail_url
    ) {
      setThumbnailLocalUrl(
        null
      );

      return;
    }

    let cancelled = false;

    let objectUrl:
      | string
      | null = null;

    void getMediaThumbnailBlob(
      media.id,
    )
      .then((blob) => {
        if (cancelled) {
          return;
        }

        objectUrl =
          URL.createObjectURL(
            blob,
          );

        setThumbnailLocalUrl(
          objectUrl,
        );
      })
      .catch(() => {
        // Original media remains the fallback.
      });

    return () => {
      cancelled = true;

      if (objectUrl) {
        URL.revokeObjectURL(
          objectUrl,
        );
      }
    };
  }, [
    media.id,
    media.thumbnail_available,
    media.thumbnail_url,
  ]);


  const originalSource =
    media.download_url ??
    originalLocalUrl;

  const thumbnailSource =
    media.thumbnail_url ??
    thumbnailLocalUrl;

  const status =
    derivativeStatus(
      media
    );

  const duration =
    readableDuration(
      media.duration_seconds
    );


  return (
    <article className="media-card">
      <div className="media-preview">
        {!originalSource &&
          !previewError && (
            <div className="media-preview-loading">
              Loading…
            </div>
          )}

        {previewError && (
          <div className="media-preview-loading">
            Preview unavailable
          </div>
        )}

        {originalSource &&
          media.media_type ===
            "image" && (
            <img
              src={
                thumbnailSource ??
                originalSource
              }
              alt={
                media.caption ??
                media.original_filename
              }
              loading="lazy"
            />
          )}

        {originalSource &&
          media.media_type ===
            "video" && (
            <div className="media-video-wrap">
              <video
                src={
                  originalSource
                }
                poster={
                  thumbnailSource ??
                  undefined
                }
                controls
                preload="metadata"
              />

              {!thumbnailSource && (
                <div className="media-video-badge">
                  <Play
                    size={12}
                  />
                  Video
                </div>
              )}
            </div>
          )}
      </div>

      {(
        status === "queued" ||
        status === "processing"
      ) && (
        <div className="media-processing-note">
          Creating preview…
        </div>
      )}

      {status === "failed" && (
        <button
          type="button"
          className="media-processing-failed"
          onClick={onRetry}
        >
          Preview processing failed.
          Retry
        </button>
      )}

      {media.caption && (
        <p className="media-card-caption">
          {media.caption}
        </p>
      )}

      <div className="media-card-footer">
        <div>
          <strong>
            {media.original_filename}
          </strong>

          <span>
            {[
              readableSize(
                media.size_bytes,
              ),
              media.width &&
              media.height
                ? `${media.width}×${media.height}`
                : null,
              duration,
            ]
              .filter(Boolean)
              .join(" · ")}
          </span>
        </div>

        <button
          type="button"
          className="media-delete-button"
          onClick={onDelete}
          aria-label="Delete media"
        >
          <Trash2 size={15} />
        </button>
      </div>
    </article>
  );
}
