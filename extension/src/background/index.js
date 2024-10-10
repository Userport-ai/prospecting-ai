import { runtime, tabs, storage } from "webextension-polyfill";
import { initializeApp } from "firebase/app";
import {
  getAuth,
  signInWithCustomToken,
  onAuthStateChanged,
} from "firebase/auth/web-extension";

// Module constants.
const loginTabIdKey = "login-tab-id";

// Global auth object.
var auth;
runtime.onInstalled.addListener(() => {
  console.log("[background] loaded ");

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

  // Initialize Firebase and get auth object.
  const app = initializeApp(firebaseConfig);
  auth = getAuth(app);
  listenToAuthChanges(auth);
});

// Listen to auth changes related to a user's login status.
function listenToAuthChanges(auth) {
  onAuthStateChanged(auth, (authUser) => {
    if (authUser !== null) {
      console.log("user is logged in AUTH LISTENER");
    } else {
      console.log("user is logged out in AUTH LISTENER");
    }
  });
}

// Handle messages from Popup App and Content Script.
runtime.onMessage.addListener((request, sender, sendResponse) => {
  const extensionId = sender.id;
  // Handle login request from user. Open userport in a new tab and log them in.
  if (request.action === "login-user") {
    // Remove existing listeners if any.
    runtime.onMessageExternal.removeListener(handleUserLoginUpdate);
    tabs.onRemoved.removeListener(handleUserLoginTabClosed);

    tabs
      .create({ url: "localhost:3000/login?source=extension", active: true })
      .then((tab) => {
        // Store tab ID for login. Delete it when tab is closed or login is complete.
        storage.local.set({ [loginTabIdKey]: tab.id }).then(() => {
          // Add listener to listen to updates of user login.
          runtime.onMessageExternal.addListener(handleUserLoginUpdate);

          // Add listener for tab closed.
          tabs.onRemoved.addListener(handleUserLoginTabClosed);
        });
      });
  }
});

// Handle messages related to user login from Userport login page.
function handleUserLoginUpdate(request, sender, sendResponse) {
  if (!("event" in request)) {
    // Not a relevant request, do nothing.
    return sendResponse();
  }

  if (request.event === "ping") {
    // Do nothing since this is just a health check from web page.
    return sendResponse();
  }

  if (request.event === "logged-in") {
    if (!("token" in request)) {
      // Token not found in request, log error.
      console.log(
        `Error: Token not found in web page message! Request: ${request}, Sender: ${sender}`
      );
      return sendResponse();
    }

    // Login user.
    signInWithCustomToken(auth, request.token)
      .then((userCredential) => {
        const user = userCredential.user;
        console.log("user logged in successfully: ", user);
      })
      .finally(() => {
        // Close Login tab. Cleaning up state will be done in close tab handler.
        const item = storage.local.get([loginTabIdKey]).then((item) => {
          const tabId = item[loginTabIdKey];
          tabs.remove(tabId);
        });
      });

    return sendResponse();
  }

  throw { message: `Unidentified event request: ${request}` };
}

// Handle logic for when user login tab is closed.
function handleUserLoginTabClosed(tabId, removeInfo) {
  storage.local.get([loginTabIdKey]).then((item) => {
    if (tabId === item[loginTabIdKey]) {
      // Login Tab is shut down.

      // Remove listener for user login updates since tab is closed.
      runtime.onMessageExternal.removeListener(handleUserLoginUpdate);

      // Close self as well.
      tabs.onRemoved.removeListener(handleUserLoginTabClosed);

      // Delete tab Id from storage.
      storage.local.remove([loginTabIdKey]);
      console.log("deleted login tab id: ", tabId);
    }
  });
}

export {};
