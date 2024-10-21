import { initializeApp } from "firebase/app";
import { getAuth, onAuthStateChanged } from "firebase/auth/web-extension";
// No external code loading possible (this disables all extensions such as Replay, Surveys, Exceptions etc.)
// Reference: https://posthog.com/docs/libraries/js.
import posthog from "posthog-js/dist/module.no-external";

// Module level variable.
var auth;
var user;

// Return Firebase auth object.
export function getAuthObj() {
  return auth;
}

// Return auth user object. It is null if logged out and present otherwise.
export function getUserObj() {
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

  auth = getAuth(app);
  listenToAuthChanges();
}

// Listen to auth changes related to a user's login status.
function listenToAuthChanges() {
  onAuthStateChanged(auth, (authUser) => {
    user = authUser;
    if (authUser !== null) {
      console.log("Auth update: user is logged in");

      // User is logged in.
      posthog.identify(authUser.uid, {
        name: authUser.displayName,
        email: authUser.email,
        emailVerified: authUser.emailVerified,
      });

      // Send event.
      posthog.capture("extension_user_logged_in");
    } else {
      console.log("Auth update: user is logged out");

      // Reset posthog identification of the user.
      posthog.reset();
    }
  });
}
