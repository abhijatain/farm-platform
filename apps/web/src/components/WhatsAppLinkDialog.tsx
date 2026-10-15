/**
 * Farmer-facing, Firebase-authenticated WhatsApp account linking dialog.
 *
 * Linking requires two-channel proof: this UI requests a temporary code,
 * then a signed incoming WhatsApp LINK message must originate from the same
 * phone verified in Firebase. Display the code once; never persist it.
 */
import { useEffect, useState } from "react";
import { CheckCircle2, CircleAlert, Copy, Link2, RefreshCcw, ShieldCheck, X } from "lucide-react";

import {
  beginWhatsAppLink,
  disconnectWhatsApp,
  getWhatsAppLinkStatus,
  type WhatsAppLanguage,
  type WhatsAppLinkChallenge,
  type WhatsAppLinkStatus,
} from "../lib/whatsapp-api";
import { useAuth } from "../providers/AuthProvider";
import "./WhatsAppLinkDialog.css";

type Props = {
  onClose: () => void;
};

const LANGUAGE_OPTIONS: { value: WhatsAppLanguage; label: string }[] = [
  { value: "pa", label: "ਪੰਜਾਬੀ · Punjabi" },
  { value: "hi", label: "हिन्दी · Hindi" },
  { value: "en", label: "English" },
];

const LANGUAGE_LABELS: Record<WhatsAppLanguage, string> = {
  pa: "Punjabi",
  hi: "Hindi",
  en: "English",
};

function formatExpiry(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? "within 10 minutes"
    : parsed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function WhatsAppLinkDialog({ onClose }: Props) {
  const { profile, user, logout } = useAuth();

  const [link, setLink] = useState<WhatsAppLinkStatus | null>(null);
  const [language, setLanguage] = useState<WhatsAppLanguage>("pa");
  const [consented, setConsented] = useState(false);
  const [challenge, setChallenge] = useState<WhatsAppLinkChallenge | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<"start" | "disconnect" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    void getWhatsAppLinkStatus()
      .then((result) => {
        if (!active) return;
        setLink(result);
        if (result.preferred_language) setLanguage(result.preferred_language);
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : "Unable to load WhatsApp status.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => { active = false; };
  }, []);

  // A real Meta webhook can complete linking while this dialog is open.
  useEffect(() => {
    if (link?.status !== "pending") return;

    let active = true;
    const handle = window.setInterval(() => {
      void getWhatsAppLinkStatus().then((result) => {
        if (!active) return;
        setLink(result);
        if (result.status === "linked") {
          setChallenge(null);
          setCopyStatus(null);
        }
      }).catch(() => {
        // Polling is best-effort; the manual Refresh button reports errors.
      });
    }, 7000);

    return () => {
      active = false;
      window.clearInterval(handle);
    };
  }, [link?.status]);

  useEffect(() => {
    function onEscape(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onEscape);
    return () => window.removeEventListener("keydown", onEscape);
  }, [onClose]);

  async function refresh() {
    setError(null);
    setLoading(true);
    try {
      const result = await getWhatsAppLinkStatus();
      setLink(result);
      if (result.status !== "pending") setChallenge(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to refresh status.");
    } finally {
      setLoading(false);
    }
  }

  async function startLink() {
    if (!consented || busy) return;
    setError(null);
    setBusy("start");
    setChallenge(null);
    setCopyStatus(null);
    try {
      const issued = await beginWhatsAppLink(language);
      setChallenge(issued);
      setLink({
        status: "pending",
        preferred_language: language,
        wa_id_last4: null,
        consent_at: null,
        code_expires_at: issued.expires_at,
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to start linking.");
    } finally {
      setBusy(null);
    }
  }

  async function unlink() {
    if (busy || !window.confirm("Disconnect WhatsApp and revoke service-message consent?")) return;
    setError(null);
    setBusy("disconnect");
    try {
      await disconnectWhatsApp();
      setLink({
        status: "revoked",
        preferred_language: language,
        wa_id_last4: null,
        consent_at: null,
        code_expires_at: null,
      });
      setChallenge(null);
      setCopyStatus(null);
      setConsented(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to disconnect WhatsApp.");
    } finally {
      setBusy(null);
    }
  }

  async function copyCommand() {
    if (!challenge) return;
    try {
      await navigator.clipboard.writeText(`LINK ${challenge.link_code}`);
      setCopyStatus("Copied. Paste this message into WhatsApp.");
    } catch {
      setCopyStatus("Copy unavailable. Select and copy the command below manually.");
    }
  }

  const state = link?.status;
  const pending = state === "pending";
  const linked = state === "linked";
  const phone = profile?.phone_e164 ?? user?.phoneNumber ?? "your Firebase-verified number";

  return (
    <div className="modal-backdrop whatsapp-modal-backdrop">
      <section
        className="whatsapp-link-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="whatsapp-dialog-title"
      >
        <header className="whatsapp-dialog-heading">
          <div className="whatsapp-icon"><Link2 size={22} aria-hidden="true" /></div>
          <div className="whatsapp-dialog-heading-text">
            <h2 id="whatsapp-dialog-title">Connect WhatsApp</h2>
            <p>Link your verified phone to receive Farm Platform messages.</p>
          </div>
          <button
            type="button"
            className="whatsapp-icon-button"
            onClick={onClose}
            aria-label="Close WhatsApp settings"
          ><X size={19} /></button>
        </header>

        <div className="whatsapp-dialog-content">
          <div className="whatsapp-status-line">
            <span className={`whatsapp-status whatsapp-status-${state ?? "unknown"}`}>
              {linked ? "Connected" : pending ? "Awaiting WhatsApp message" : loading ? "Checking connection…" : "Not connected"}
            </span>
            <button
              className="whatsapp-refresh"
              type="button"
              disabled={loading || busy !== null}
              onClick={() => void refresh()}
            >
              <RefreshCcw size={15} aria-hidden="true" /> Refresh status
            </button>
          </div>

          {error && <p className="whatsapp-error" role="alert"><CircleAlert size={16} />{error}</p>}

          {linked ? (
            <div className="whatsapp-result" role="status">
              <CheckCircle2 className="whatsapp-success-icon" size={29} />
              <h3>WhatsApp is linked</h3>
              <p>Connected WhatsApp number ending in <strong>{link?.wa_id_last4}</strong>.</p>
              <p>Language: <strong>{LANGUAGE_LABELS[link?.preferred_language ?? "en"]}</strong></p>
              <p className="whatsapp-muted">Service messages only. You can disconnect at any time.</p>
              <button className="whatsapp-danger-button" disabled={busy !== null} onClick={() => void unlink()}>
                {busy === "disconnect" ? "Disconnecting…" : "Disconnect WhatsApp"}
              </button>
            </div>
          ) : pending ? (
            <div className="whatsapp-pending">
              <h3>One more step</h3>
              <p>From <strong>{phone}</strong>, send the following message to <strong>{challenge?.business_phone_e164 ?? "the WhatsApp number configured in Meta"}</strong>.</p>
              {challenge ? (
                <>
                  <label htmlFor="whatsapp-link-command">Your one-time linking message</label>
                  <div className="whatsapp-code-row">
                    <input
                      id="whatsapp-link-command"
                      value={`LINK ${challenge.link_code}`}
                      readOnly
                      aria-label="One-time WhatsApp linking message"
                      onFocus={(event) => event.currentTarget.select()}
                    />
                    <button type="button" className="whatsapp-copy-button" onClick={() => void copyCommand()}>
                      <Copy size={16} aria-hidden="true" /> Copy
                    </button>
                  </div>
                  {copyStatus && <p className="whatsapp-muted" role="status">{copyStatus}</p>}
                </>
              ) : (
                <p className="whatsapp-muted">
                  A code was already issued. For security it is shown only once.
                  If you no longer have it, generate a new code below.
                </p>
              )}
              <p className="whatsapp-expiry">
                {challenge || link?.code_expires_at
                  ? `Expires at ${formatExpiry(challenge?.expires_at ?? link?.code_expires_at ?? "")}`
                  : "Code expires ten minutes after issue."}
              </p>
              <p className="whatsapp-muted">
                Status updates automatically after a verified incoming WhatsApp message.
                Meta dashboard samples alone cannot prove ownership of your real phone.
              </p>
              <div className="whatsapp-pending-actions">
                <button className="secondary-action" type="button" disabled={busy !== null || loading} onClick={() => void refresh()}>
                  Check now
                </button>
                <button className="whatsapp-danger-button" type="button" disabled={busy !== null} onClick={() => void unlink()}>
                  Cancel linking
                </button>
              </div>
              <p className="whatsapp-muted">Lost the code? Cancel linking and start again.</p>
            </div>
          ) : (
            <div className="whatsapp-form">
              <p className="whatsapp-description">
                Your Farm Platform account uses <strong>{phone}</strong>.
                For your safety, linking only succeeds when your incoming WhatsApp
                message comes from that same number.
              </p>
              <button
                type="button"
                className="whatsapp-refresh"
                onClick={() => void logout()}
              >
                Is this a test number? Sign out and use my real phone
              </button>

              <label className="whatsapp-form-label" htmlFor="whatsapp-language">Preferred message language</label>
              <select
                id="whatsapp-language"
                className="whatsapp-select"
                value={language}
                disabled={loading || busy !== null}
                onChange={(event) => setLanguage(event.target.value as WhatsAppLanguage)}
              >
                {LANGUAGE_OPTIONS.map((option) => (
                  <option value={option.value} key={option.value}>{option.label}</option>
                ))}
              </select>

              <label className="whatsapp-consent">
                <input
                  type="checkbox"
                  checked={consented}
                  disabled={loading || busy !== null}
                  onChange={(event) => setConsented(event.target.checked)}
                />
                <span>
                  I agree to receive Farm Platform service messages on WhatsApp.
                  This does not include marketing messages, and I can revoke consent anytime.
                </span>
              </label>

              <div className="whatsapp-privacy-note">
                <ShieldCheck size={19} aria-hidden="true" />
                <p>We verify your number using a short-lived code. Your WhatsApp chat content is not saved for linking.</p>
              </div>

              <button
                type="button"
                className="primary-action full"
                disabled={!consented || loading || busy !== null || link === null}
                onClick={() => void startLink()}
              >
                {busy === "start" ? "Generating code…" : "Generate linking code"}
              </button>
            </div>
          )}
        </div>

        <footer className="whatsapp-dialog-footer">
          <span>Development feature · automated replies are not available yet</span>
          <button type="button" className="secondary-action" onClick={onClose}>Close</button>
        </footer>
      </section>
    </div>
  );
}
