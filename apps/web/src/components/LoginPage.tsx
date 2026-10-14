import {
  useRef,
  useState,
} from "react";

import {
  Activity,
  Map,
  Satellite,
  ShieldCheck,
  Sprout,
} from "lucide-react";

import {
  type ConfirmationResult,
  RecaptchaVerifier,
  signInWithPhoneNumber,
} from "firebase/auth";

import {
  auth,
} from "../lib/firebase";


export default function LoginPage() {
  const [
    phone,
    setPhone,
  ] = useState(
    "+91",
  );

  const [
    code,
    setCode,
  ] = useState(
    "",
  );

  const [
    confirmation,
    setConfirmation,
  ] = useState<
    ConfirmationResult | null
  >(
    null,
  );

  const [
    loading,
    setLoading,
  ] = useState(
    false,
  );

  const [
    error,
    setError,
  ] = useState<
    string | null
  >(
    null,
  );

  const verifierRef =
    useRef<
      RecaptchaVerifier | null
    >(
      null,
    );


  async function sendOtp() {
    try {
      setLoading(
        true,
      );

      setError(
        null,
      );

      verifierRef.current
        ?.clear();

      const verifier =
        new RecaptchaVerifier(
          auth,
          "recaptcha-container",
          {
            size:
              "invisible",
          },
        );

      verifierRef.current =
        verifier;

      const result =
        await signInWithPhoneNumber(
          auth,
          phone.replace(
            /\s+/g,
            "",
          ),
          verifier,
        );

      setConfirmation(
        result,
      );

    } catch (
      requestError
    ) {
      setError(
        requestError
          instanceof Error
          ? requestError.message
          : "Unable to send OTP.",
      );

    } finally {
      setLoading(
        false,
      );
    }
  }


  async function verifyOtp() {
    if (
      !confirmation
    ) {
      return;
    }

    try {
      setLoading(
        true,
      );

      setError(
        null,
      );

      await confirmation
        .confirm(
          code,
        );

    } catch (
      requestError
    ) {
      setError(
        requestError
          instanceof Error
          ? requestError.message
          : "Invalid OTP.",
      );

    } finally {
      setLoading(
        false,
      );
    }
  }


  return (
    <main className="landing-page">
      <section className="landing-hero">
        <div className="landing-brand">
          <div className="landing-brand-mark">
            <Sprout
              size={22}
            />
          </div>

          <strong>
            Farm Platform
          </strong>
        </div>

        <div className="landing-copy">
          <span className="landing-eyebrow">
            FIELD INTELLIGENCE
          </span>

          <h1>
            See every field.
            <br />
            Know what changed.
          </h1>

          <p>
            Bring farm boundaries, crop records, activities and multi-source
            satellite monitoring into one clear workspace.
          </p>

          <div className="landing-feature-grid">
            <div>
              <Map
                size={19}
              />

              <strong>
                One farm map
              </strong>

              <span>
                View every field boundary and condition together.
              </span>
            </div>

            <div>
              <Satellite
                size={19}
              />

              <strong>
                Optical + radar
              </strong>

              <span>
                Sentinel-2, all-weather Sentinel-1 and Landsat thermal.
              </span>
            </div>

            <div>
              <Activity
                size={19}
              />

              <strong>
                Field history
              </strong>

              <span>
                Keep crop activities and satellite observations connected.
              </span>
            </div>
          </div>
        </div>

        <div className="landing-trust">
          <ShieldCheck
            size={16}
          />

          <span>
            Your farm data stays private to your account.
          </span>
        </div>
      </section>

      <section className="landing-login">
        <div className="landing-login-card">
          <span className="landing-login-kicker">
            FARMER LOGIN
          </span>

          <h2>
            Welcome back
          </h2>

          <p>
            Sign in with the mobile number linked to your farm account.
          </p>

          {!confirmation
            ? (
              <>
                <label>
                  Mobile number
                </label>

                <input
                  className="form-input"
                  inputMode="tel"
                  value={
                    phone
                  }
                  onChange={(
                    event,
                  ) =>
                    setPhone(
                      event.target
                        .value,
                    )
                  }
                  placeholder="+91 98765 43210"
                />

                <button
                  id="phone-login-button"
                  className="primary-action landing-login-action"
                  disabled={
                    loading
                  }
                  onClick={
                    sendOtp
                  }
                >
                  {loading
                    ? "Sending OTP…"
                    : "Continue with phone"}
                </button>
              </>
            )
            : (
              <>
                <div className="landing-phone-sent">
                  Code sent to {phone}
                </div>

                <label>
                  Verification code
                </label>

                <input
                  className="form-input login-code-input"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  value={
                    code
                  }
                  onChange={(
                    event,
                  ) =>
                    setCode(
                      event.target
                        .value,
                    )
                  }
                  placeholder="123456"
                />

                <button
                  className="primary-action landing-login-action"
                  disabled={
                    loading
                  }
                  onClick={
                    verifyOtp
                  }
                >
                  {loading
                    ? "Verifying…"
                    : "Open farm dashboard"}
                </button>

                <button
                  className="text-button landing-change-phone"
                  onClick={
                    () => {
                      setConfirmation(
                        null,
                      );

                      setCode(
                        "",
                      );
                    }
                  }
                >
                  Use a different number
                </button>
              </>
            )}

          {error && (
            <div className="login-error">
              {error}
            </div>
          )}

          <p className="login-disclosure">
            Firebase processes your phone number for authentication and abuse
            prevention.
          </p>

          <div
            id="recaptcha-container"
          />
        </div>
      </section>
    </main>
  );
}
