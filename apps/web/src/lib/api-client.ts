import { auth } from "./firebase";

const API_URL =
  import.meta.env.VITE_API_URL;

if (!API_URL) {
  throw new Error(
    "VITE_API_URL is missing.",
  );
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
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
          typeof body.detail === "string"
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

  return (
    response.json() as Promise<T>
  );
}
