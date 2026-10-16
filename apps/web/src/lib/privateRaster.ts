import { useEffect, useState } from "react";
import { auth } from "./firebase";

const API_URL = import.meta.env.VITE_API_URL;

/** Fetch a private image with the current Firebase bearer token.
 * Image tags cannot attach Authorization headers; short-lived blob URLs keep
 * the raw tiler/storage URL off the device and are revoked on cleanup.
 */
export function usePrivateRaster(path: string | null) {
  const [result, setResult] = useState<{
    path: string | null;
    url: string | null;
    loading: boolean;
    error: string | null;
  }>({ path: null, url: null, loading: false, error: null });

  useEffect(() => {
    if (!path) return;
    let cancelled = false;
    let url: string | null = null;
    const controller = new AbortController();

    async function load() {
      setResult({ path, url: null, loading: true, error: null });
      try {
        const user = auth.currentUser;
        if (!user) throw new Error("Sign in to view satellite imagery.");
        const token = await user.getIdToken();
        if (cancelled) return;
        const response = await fetch(`${API_URL}${path}`, {
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
          cache: "no-store",
        });
        if (!response.ok) throw new Error("Satellite preview is unavailable. Check that the local tiler is running.");
        const blob = await response.blob();
        if (cancelled) return;
        if (blob.type !== "image/png" || blob.size === 0) throw new Error("Unexpected image response.");
        url = URL.createObjectURL(blob);
        setResult({ path, url, loading: false, error: null });
      } catch (error) {
        if (!cancelled) setResult({
          path, url: null, loading: false,
          error: error instanceof Error ? error.message : "Unable to load raster preview.",
        });
      }
    }

    void load();
    return () => {
      cancelled = true;
      controller.abort();
      if (url) URL.revokeObjectURL(url);
    };
  }, [path]);

  return result.path === path
    ? result
    : { path, url: null, loading: Boolean(path), error: null };
}
