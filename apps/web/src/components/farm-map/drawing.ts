import {
  TerraDraw,
  TerraDrawPolygonMode,
  TerraDrawSelectMode,
} from "terra-draw";
import { TerraDrawMapLibreGLAdapter } from "terra-draw-maplibre-gl-adapter";
import type { Map as MapLibreMap } from "maplibre-gl";
import type { PolygonGeometry } from "../../types/api";

type Options = {
  map: MapLibreMap;
  drawing: boolean;
  onPolygonFinished: (boundary: PolygonGeometry) => void;
};

export function createDrawingSystem({
  map,
  drawing,
  onPolygonFinished,
}: Options) {
  const draw = new TerraDraw({
    adapter: new TerraDrawMapLibreGLAdapter({ map }),
    modes: [
      new TerraDrawPolygonMode({ showCoordinatePoints: true }),
      new TerraDrawSelectMode({
        flags: {
          polygon: {
            feature: {
              draggable: true,
              coordinates: {
                draggable: true,
                deletable: true,
                midpoints: true,
              },
            },
          },
        },
      }),
    ],
  });

  draw.start();

  try {
    draw.setMode(drawing ? "polygon" : "select");
  } catch (error) {
    console.error("Unable to set TerraDraw mode:", error);
  }

  draw.on("finish", (id, context) => {
    if (context.action !== "draw") {
      return;
    }

    const feature = draw
      .getSnapshot()
      .find((candidate) => candidate.id === id);

    if (!feature || feature.geometry.type !== "Polygon") {
      return;
    }

    const boundary: PolygonGeometry = {
      type: "Polygon",
      coordinates: feature.geometry.coordinates as number[][][],
    };

    onPolygonFinished(boundary);
    draw.clear();

    try {
      draw.setMode("select");
    } catch (error) {
      console.error("Unable to leave polygon mode:", error);
    }
  });

  return draw;
}
