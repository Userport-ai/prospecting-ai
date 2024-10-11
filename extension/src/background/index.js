import { runtime, tabs, storage } from "webextension-polyfill";
import { initializeApp } from "firebase/app";
import {
  getAuth,
  signInWithCustomToken,
  onAuthStateChanged,
} from "firebase/auth/web-extension";

// Module constants.
const loginTabIdKey = "login-tab-id";
const authUserObjectKey = "auth-user-object";

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

function getUser(idToken) {
  fetch("https://8f43-223-185-130-56.ngrok-free.app/api/v1/users", {
    headers: { Authorization: "Bearer " + idToken },
  })
    .then((response) => response.json())
    .then((result) => {
      console.log("Got USER fetch result: ", result);
    });
}

// Listen to auth changes related to a user's login status.
function listenToAuthChanges(auth) {
  onAuthStateChanged(auth, (authUser) => {
    if (authUser !== null) {
      console.log("Auth update: user is logged");
      authUser.getIdToken().then((idToken) => getUser(idToken));
    } else {
      console.log("Auth update: user is logged out");
    }
    updateUserObjectInStorage(authUser);
  });
}

// Read user object from storage. Returns null if user is logged out or hasn't signed in yet.
async function readUserObjectFromStorage() {
  const item = await storage.local.get([authUserObjectKey]);
  if (authUserObjectKey in item) {
    return item[authUserObjectKey];
  }
  // User object does not exist, return null.
  console.log("User object does not exist in storage.");
  return null;
}

// Update given user object (can be null if user is logged out) to storage.
function updateUserObjectInStorage(user) {
  storage.local.set({ [authUserObjectKey]: user });
}

// Handle messages from Popup App and Content Script.
runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "fetch-user") {
    // Fetch user object from storage and return to the caller.
    readUserObjectFromStorage().then((user) => sendResponse(user));

    // Since the user fetch is async, we return true to wait for async process to complete.
    // Reference: https://developer.chrome.com/docs/extensions/develop/concepts/messaging.
    return true;
  }
  if (request.action === "login-user") {
    // Handle login request from user. Open userport in a new tab and log them in.

    // Remove existing listeners if any.
    runtime.onMessageExternal.removeListener(handleUserLoginUpdate);
    tabs.onRemoved.removeListener(handleUserLoginTabClosed);

    tabs
      .create({
        url: `${process.env.REACT_APP_HOSTNAME}/login?source=extension`,
        active: true,
      })
      .then((tab) => {
        // Store tab ID for login. Delete it when tab is closed or login is complete.
        storage.local.set({ [loginTabIdKey]: tab.id }).then(() => {
          // Add listener to listen to updates of user login.
          runtime.onMessageExternal.addListener(handleUserLoginUpdate);

          // Add listener for tab closed.
          tabs.onRemoved.addListener(handleUserLoginTabClosed);
        });
      });
    return;
  }

  if (request.action === "view-all-leads") {
    // Navigate user to new tab to view all the leads they have researched so far.
    tabs.create({
      url: `${process.env.REACT_APP_HOSTNAME}/leads`,
      active: true,
    });
    return;
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

        // Save authenticated user to storage.
        updateUserObjectInStorage(user);
      })
      .finally(() => {
        // Close Login tab. Cleaning up state will be done in close tab handler.
        storage.local.get([loginTabIdKey]).then((item) => {
          const tabId = item[loginTabIdKey];
          tabs.remove(tabId);
        });
      });

    return sendResponse();
  }

  throw Error(`Unidentified event request: ${request}`);
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
