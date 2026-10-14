import {
  useMemo,
} from "react";

import type {
  PolygonGeometry,
} from "../types/api";


type Props = {
  boundary: PolygonGeometry;

  className?: string;
};


function normalizeBoundary(
  boundary: PolygonGeometry,
) {
  const ring =
    boundary.coordinates[
      0
    ]
    ?? [];

  if (
    ring.length === 0
  ) {
    return "";
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

  const width =
    Math.max(
      maxX - minX,
      0.000001,
    );

  const height =
    Math.max(
      maxY - minY,
      0.000001,
    );

  const boxWidth =
    152;

  const boxHeight =
    92;

  const padding =
    10;

  const usableWidth =
    boxWidth
    - padding * 2;

  const usableHeight =
    boxHeight
    - padding * 2;

  const scale =
    Math.min(
      usableWidth
        / width,
      usableHeight
        / height,
    );

  const renderedWidth =
    width * scale;

  const renderedHeight =
    height * scale;

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

  return ring
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
}


export default function FieldBoundaryPreview({
  boundary,
  className = "",
}: Props) {
  const points =
    useMemo(
      () =>
        normalizeBoundary(
          boundary,
        ),
      [
        boundary,
      ],
    );

  return (
    <svg
      className={
        `field-boundary-preview ${className}`
      }
      viewBox="0 0 152 92"
      role="img"
      aria-label="Field boundary"
    >
      <polygon
        points={points}
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
