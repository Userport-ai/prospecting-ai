import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth/web-extension";
import { captureEvent, identifyUser, resetUserIdentification } from "./metrics";

// Return Firebase auth object.
export async function getAuthObj() {
  const auth = initAuth();
  await auth.authStateReady();
  return auth;
}

// Return auth user object. If non null, user is logged in and if null, user is logged out.
// Checking currentUser from auth object requires auth object to be initialized. That's why
// we wait for authStateReady() before reading currentUser object.
// Reference: https://firebase.google.com/docs/auth/web/manage-users#get_the_currently_signed-in_user.
// https://firebase.google.com/docs/reference/js/auth.auth.md#authauthstateready
export async function getUserObj() {
  const auth = await getAuthObj();
  const user = auth.currentUser;
  if (user !== null) {
    console.log("Auth: user is logged in: ", user.email);

    // Idenfity User as logged in.
    identifyUser(user.uid, {
      name: user.displayName,
      email: user.email,
      emailVerified: user.emailVerified,
    });

    // Send event.
    captureEvent("extension_user_logged_in");
  } else {
    console.log("Auth update: user is logged out");

    // Reset identification of the user.
    resetUserIdentification();
  }
  return user;
}

export function initAuth() {
  // Initialize firebase.
  const firebaseConfig = {
    apiKey: process.env.REACT_APP_FIREBASE_API_KEY,
    authDomain: process.env.REACT_APP_FIREBASE_AUTH_DOMAIN,
    projectId: process.env.REACT_APP_FIREBASE_PROJECT_ID,
    storageBucket: process.env.REACT_APP_FIREBASE_STORAGE_BUCKET,
    messagingSenderId: process.env.REACT_APP_FIREBASE_MESSAGING_SENDER_ID,
    appId: process.env.REACT_APP_FIREBASE_APP_ID,
    measurementId: process.env.REACT_APP_FIREBASE_MEASUREMENT_ID,
  };
  const app = initializeApp(firebaseConfig);
  return getAuth(app);
}
