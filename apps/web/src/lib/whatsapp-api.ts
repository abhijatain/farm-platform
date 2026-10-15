/**
 * Authenticated farmer-owned WhatsApp linking endpoints.
 *
 * These requests reuse the app's Firebase bearer token via apiRequest; Meta
 * app secrets and linking codes are never stored in browser storage.
 */
import { apiRequest } from "./api-client";

export type WhatsAppLanguage = "pa" | "hi" | "en";
export type WhatsAppLinkState = "unlinked" | "pending" | "linked" | "revoked";

export type WhatsAppLinkStatus = {
  status: WhatsAppLinkState;
  preferred_language: WhatsAppLanguage | null;
  wa_id_last4: string | null;
  consent_at: string | null;
  code_expires_at: string | null;
};

export type WhatsAppLinkChallenge = {
  link_code: string;
  expires_at: string;
  instructions: string;
};

const PATH = "/whatsapp/link";

export function getWhatsAppLinkStatus() {
  return apiRequest<WhatsAppLinkStatus>(PATH, {
    cache: "no-store",
  });
}

export function beginWhatsAppLink(language: WhatsAppLanguage) {
  return apiRequest<WhatsAppLinkChallenge>(`${PATH}/start`, {
    method: "POST",
    cache: "no-store",
    body: JSON.stringify({
      consent: true,
      preferred_language: language,
    }),
  });
}

export function disconnectWhatsApp() {
  return apiRequest<void>(PATH, {
    method: "DELETE",
    cache: "no-store",
  });
}
