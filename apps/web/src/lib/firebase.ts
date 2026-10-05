import {
  getApp,
  getApps,
  initializeApp,
} from "firebase/app";

import {
  getAuth,
} from "firebase/auth";


const firebaseConfig = {

  apiKey:
    import.meta.env
      .VITE_FIREBASE_API_KEY,

  authDomain:
    import.meta.env
      .VITE_FIREBASE_AUTH_DOMAIN,

  projectId:
    import.meta.env
      .VITE_FIREBASE_PROJECT_ID,

  appId:
    import.meta.env
      .VITE_FIREBASE_APP_ID,

  messagingSenderId:
    import.meta.env
      .VITE_FIREBASE_MESSAGING_SENDER_ID,

};


if (
  !firebaseConfig.apiKey ||
  !firebaseConfig.authDomain ||
  !firebaseConfig.projectId ||
  !firebaseConfig.appId
) {
  throw new Error(
    "Firebase configuration is incomplete.",
  );
}


export const firebaseApp =
  getApps().length
    ? getApp()
    : initializeApp(
        firebaseConfig,
      );


export const auth =
  getAuth(firebaseApp);


if (
  import.meta.env
    .VITE_FIREBASE_TEST_PHONE_AUTH
  === "true"
) {
  /*
   * ONLY use with Firebase-configured
   * fictional test phone numbers.
   */
  auth.settings
    .appVerificationDisabledForTesting =
      true;
}
