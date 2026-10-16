import {
  useEffect,
  useRef,
  useState,
} from "react";

import {
  type ConfirmationResult,
  RecaptchaVerifier,
  signInWithPhoneNumber,
} from "firebase/auth";

import {
  auth,
} from "../lib/firebase";


type GrecaptchaWindow = Window & {
  grecaptcha?: {
    reset: (widgetId: number) => void;
  };
};

export default function LoginPage() {

  const [
    phone,
    setPhone,
  ] =
    useState("+91");


  const [
    code,
    setCode,
  ] =
    useState("");


  const [
    confirmation,
    setConfirmation,
  ] =
    useState<
      ConfirmationResult | null
    >(null);


  const [
    loading,
    setLoading,
  ] =
    useState(false);


  const [
    error,
    setError,
  ] =
    useState<string | null>(
      null,
    );


  const verifierRef =
    useRef<
      RecaptchaVerifier | null
    >(null);

  // Use the same verifier for repeated attempts; clearing and recreating
  // one inside the same element causes Google's "already rendered" error.
  const recaptchaElementRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    return () => {
      verifierRef.current?.clear();
      verifierRef.current = null;
    };
  }, []);


  async function sendOtp() {

    try {

      setLoading(true);
      setError(null);


      let verifier = verifierRef.current;

      if (!verifier) {
        const container = recaptchaElementRef.current;
        if (!container) {
          throw new Error("reCAPTCHA container is unavailable. Please reload.");
        }

        verifier = new RecaptchaVerifier(auth, container, {
          size: "invisible",
        });
        verifierRef.current = verifier;
      }


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
      error
    ) {

      // Firebase recommends resetting the challenge after an SMS request
      // fails. Keep the verifier and its DOM binding for the next attempt.
      if (verifierRef.current) {
        try {
          const widgetId = await verifierRef.current.render();
          (window as GrecaptchaWindow).grecaptcha?.reset(widgetId);
        } catch {
          // Do not replace the original Firebase error with a reset error.
        }
      }

      setError(
        error instanceof Error
          ? error.message
          : "Unable to send OTP.",
      );

    } finally {

      setLoading(false);

    }

  }


  async function verifyOtp() {

    if (!confirmation) {
      return;
    }


    try {

      setLoading(true);
      setError(null);


      await confirmation.confirm(
        code,
      );

      /*
       * AuthProvider will now take
       * over and App will switch to
       * the farm dashboard.
       */

    } catch (
      error
    ) {

      setError(
        error instanceof Error
          ? error.message
          : "Invalid OTP.",
      );

    } finally {

      setLoading(false);

    }

  }


  return (
    <div className="login-page">

      <div className="login-card">

        <div className="login-logo">
          🌱
        </div>


        <h1>
          Farm Platform
        </h1>


        <p className="login-subtitle">

          Your fields, crops and
          farm records in one place.

        </p>


        {!confirmation ? (
          <>

            <label>
              Mobile number
            </label>


            <input
              className="form-input"

              value={phone}

              onChange={(
                event,
              ) =>
                setPhone(
                  event
                    .target
                    .value,
                )
              }

              placeholder="+91 98765 43210"
            />


            <button
              id="phone-login-button"

              className="primary-action"

              disabled={
                loading
              }

              onClick={
                sendOtp
              }
            >

              {loading
                ? "Sending..."
                : "Send OTP"}

            </button>

          </>
        ) : (
          <>

            <label>
              Verification code
            </label>


            <input
              className="form-input"

              value={code}

              onChange={(
                event,
              ) =>
                setCode(
                  event
                    .target
                    .value,
                )
              }

              placeholder="123456"
            />


            <button
              className="primary-action"

              disabled={
                loading
              }

              onClick={
                verifyOtp
              }
            >

              {loading
                ? "Checking..."
                : "Verify"}

            </button>


            <button
              className="text-button"

              onClick={() => {
                setConfirmation(
                  null,
                );

                setCode("");
              }}
            >
              Change phone number
            </button>

          </>
        )}


        {error && (
          <div className="login-error">
            {error}
          </div>
        )}


        <p className="login-disclosure">

          Your phone number is
          processed by Firebase for
          authentication and abuse
          prevention. Use your real mobile number to link WhatsApp; Firebase
          test numbers cannot prove ownership of a real WhatsApp account.

        </p>


        <div ref={recaptchaElementRef} />

      </div>

    </div>
  );
}
