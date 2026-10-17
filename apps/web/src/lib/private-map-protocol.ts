import maplibregl from "maplibre-gl";
import { auth } from "./firebase";

// Tiles are requested with a Firebase Bearer token; never include a token,
// signed GCS URL or raw gs:// object path in TileJSON or layer definitions.
const API_URL = import.meta.env.VITE_API_URL;
const PRIVATE_TILE_RE = /^farmtile:\/\/private(\/fields\/[a-f0-9-]{36}\/satellite-observations\/[a-f0-9-]{36}\/tiles\/[a-z0-9_]+\/\d+\/\d+\/\d+\.png)$/;
let installed = false;

/** Register before MapLibre creates a map. The protocol is globally shared. */
export function registerPrivateMapProtocol() {
  if (installed) return;
  maplibregl.addProtocol("farmtile", async (params, abortController) => {
    const match = PRIVATE_TILE_RE.exec(params.url);
    if (!match) throw new Error("Invalid private tile URL.");
    if (!auth.currentUser) throw new Error("Not authenticated for field tiles.");
    const token = await auth.currentUser.getIdToken();
    const response = await fetch(`${API_URL}${match[1]}`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: abortController.signal,
      cache: "no-store",
    });
    if (!response.ok) throw new Error(`Private satellite tile request failed: ${response.status}`);
    return { data: new Uint8Array(await response.arrayBuffer()) };
  });
  installed = true;
}
