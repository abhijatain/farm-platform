import {
  useId,
  useMemo,
} from "react";

import type {
  PolygonGeometry,
} from "../types/api";


type Props = {
  boundary: PolygonGeometry;

  imageUrl?: string | null;

  className?: string;
};


type NormalizedBoundary = {
  points: string;

  x: number;
  y: number;

  width: number;
  height: number;
};


function normalizeBoundary(
  boundary: PolygonGeometry,
): NormalizedBoundary {
  const ring =
    boundary.coordinates[
      0
    ]
    ?? [];

  const boxWidth =
    152;

  const boxHeight =
    92;

  const padding =
    10;

  if (
    ring.length === 0
  ) {
    return {
      points:
        "",

      x:
        padding,

      y:
        padding,

      width:
        boxWidth
        - padding * 2,

      height:
        boxHeight
        - padding * 2,
    };
  }

  const xs =
    ring.map(
      (
        point,
      ) =>
        point[
          0
        ],
    );

  const ys =
    ring.map(
      (
        point,
      ) =>
        point[
          1
        ],
    );

  const minX =
    Math.min(
      ...xs,
    );

  const maxX =
    Math.max(
      ...xs,
    );

  const minY =
    Math.min(
      ...ys,
    );

  const maxY =
    Math.max(
      ...ys,
    );

  const sourceWidth =
    Math.max(
      maxX - minX,
      0.000001,
    );

  const sourceHeight =
    Math.max(
      maxY - minY,
      0.000001,
    );

  const usableWidth =
    boxWidth
    - padding * 2;

  const usableHeight =
    boxHeight
    - padding * 2;

  const scale =
    Math.min(
      usableWidth
        / sourceWidth,
      usableHeight
        / sourceHeight,
    );

  const renderedWidth =
    sourceWidth
    * scale;

  const renderedHeight =
    sourceHeight
    * scale;

  const offsetX =
    (
      boxWidth
      - renderedWidth
    )
    / 2;

  const offsetY =
    (
      boxHeight
      - renderedHeight
    )
    / 2;

  const points =
    ring
      .map(
        (
          [
            longitude,
            latitude,
          ],
        ) => {
          const x =
            offsetX
            + (
              longitude
              - minX
            )
            * scale;

          const y =
            boxHeight
            - (
              offsetY
              + (
                latitude
                - minY
              )
              * scale
            );

          return (
            `${x.toFixed(2)},${y.toFixed(2)}`
          );
        },
      )
      .join(
        " ",
      );

  return {
    points,

    x:
      offsetX,

    y:
      offsetY,

    width:
      renderedWidth,

    height:
      renderedHeight,
  };
}


export default function FieldBoundaryPreview({
  boundary,
  imageUrl = null,
  className = "",
}: Props) {
  const id =
    useId()
      .replace(
        /:/g,
        "",
      );

  const geometry =
    useMemo(
      () =>
        normalizeBoundary(
          boundary,
        ),
      [
        boundary,
      ],
    );

  const clipId =
    `field-boundary-${id}`;

  return (
    <svg
      className={
        `field-boundary-preview ${className}`
      }
      viewBox="0 0 152 92"
      role="img"
      aria-label="Field boundary"
    >
      <defs>
        <clipPath
          id={
            clipId
          }
        >
          <polygon
            points={
              geometry.points
            }
          />
        </clipPath>
      </defs>

      {imageUrl && (
        <image
          href={
            imageUrl
          }
          x={
            geometry.x
          }
          y={
            geometry.y
          }
          width={
            geometry.width
          }
          height={
            geometry.height
          }
          preserveAspectRatio="none"
          clipPath={
            `url(#${clipId})`
          }
        />
      )}

      <polygon
        className={
          imageUrl
            ? "field-boundary-outline raster"
            : "field-boundary-outline"
        }
        points={
          geometry.points
        }
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
