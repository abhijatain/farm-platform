import {
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


  async function sendOtp() {

    try {

      setLoading(true);
      setError(null);


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
      error
    ) {

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


        <div
          id="recaptcha-container"
        />

      </div>

    </div>
  );
}
