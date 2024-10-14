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

// Global objects.
var auth;
var user;

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

  // Add tab closed listener.
  tabs.onRemoved.addListener(handleTabClosed);
});

// Listen to auth changes related to a user's login status.
function listenToAuthChanges(auth) {
  onAuthStateChanged(auth, (authUser) => {
    if (authUser !== null) {
      console.log("Auth update: user is logged in");
    } else {
      console.log("Auth update: user is logged out");
    }
    user = authUser;
  });
}

// Returns lead profile from storage. Returns null if it does not exist.
async function getLeadProfile(tabId) {
  const tabIdKey = tabId.toString();
  const item = await storage.local.get([tabIdKey]);
  if (tabIdKey in item) {
    return item[tabIdKey];
  }
  // User object does not exist, return null.
  console.log(`Lead profile not found in storage in tab ID: ${tabIdKey}`);
  return null;
}

// Return global user object. Returns null if user is logged out or hasn't signed in yet.
function getUser() {
  return user;
}

// LinkedIn profile detected in a tab, check if lead report exists for this profile.
function handleLinkedInProfileDetected(linkedInProfileUrl, tabId) {
  const encodedProfileURL = encodeURIComponent(linkedInProfileUrl);
  user
    .getIdToken()
    .then((idToken) =>
      fetch(
        `${process.env.REACT_APP_API_HOSTNAME}/api/v1/lead-research-reports?url=${encodedProfileURL}`,
        {
          headers: { Authorization: "Bearer " + idToken },
        }
      )
    )
    .then((response) => response.json())
    .then((result) => {
      if (result.status === "error") {
        console.error(
          `Checking if LinkedIn profile exists failed with result: ${result}`
        );
        return;
      }

      // Create lead profile from the result.
      const leadProfile = {
        url: linkedInProfileUrl,
        lead_research_report: result.report_exists
          ? result.lead_research_report
          : null,
      };

      // Store lead profile for given tabId. This will override existing profile
      // whenver the existing LinkedIn profile in the current tab is changed.
      // We will delete this key when the tab is closed in the listener.
      const tabIdKey = tabId.toString();
      storage.local.set({ [tabIdKey]: leadProfile });
    });
}

// Handle tab updates to know when LinkedIn URL has changed. This change is then
// passed to Content Script which can then parse the URL and return whether it is valid or not.
// We need to pass to the Content Script since service worker does not have access
// to the DOM for the specific tab.
tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  const url = tab.url;
  if (
    url.includes("linkedin.com/in/") &&
    !url.includes("?") &&
    changeInfo.status === "complete"
  ) {
    tabs
      .sendMessage(tabId, { action: "linkedin-profile-detected" })
      .then((isValidURL) => {
        if (!isValidURL) {
          // Do nothing.
          return;
        }

        handleLinkedInProfileDetected(url, tabId);
      });
  } else {
    // Delete existing lead profile from storage if tab URL has changed.
    // User should not see past profile in popup if tab is not that of a lead profile.
    const tabIdKey = tabId.toString();
    storage.local.get([tabIdKey]).then((item) => {
      if (tabIdKey in item) {
        const leadProfile = item[tabIdKey];
        if (leadProfile.url !== url) {
          // New URL detected that is not a Lead profile, delete existing lead profile from storage.
          storage.local.remove([tabIdKey]);
        }
      }
    });
  }
});

// Handle messages from Popup App and Content Script.
runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "fetch-user") {
    // Fetch user object from storage and return to the caller.
    sendResponse(getUser());

    // Since the user fetch is synchronous, we return false.
    // Reference: https://developer.chrome.com/docs/extensions/develop/concepts/messaging.
    return false;
  }
  if (request.action === "fetch-lead-profile") {
    getLeadProfile(request.tabId).then((leadProfile) =>
      sendResponse(leadProfile)
    );

    // Since the lead profile fetch is asynchronous, we return true.
    return true;
  }
  if (request.action === "login-user") {
    // Handle login request from user. Open userport in a new tab and log them in.

    // Remove existing listeners if any.
    runtime.onMessageExternal.removeListener(handleUserLoginUpdate);

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
        });
      });
    return;
  }

  if (request.action === "view-lead-report") {
    // Navigate user to new tab to view the lead report in the Userport UI.
    tabs.create({
      url: `${process.env.REACT_APP_HOSTNAME}/lead-research-reports/${request.report_id}`,
      active: true,
    });
    return;
  }

  if (request.action === "view-all-leads") {
    // Navigate user to new tab to view all the leads they have researched so far in the Userport UI.
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
        console.log("user logged in successfully: ", userCredential.user);
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

// Handle state for when user closes a tab. Usually a clean up of state is needed.
function handleTabClosed(tabId, removeInfo) {
  storage.local.get([loginTabIdKey]).then((item) => {
    if (item && tabId === item[loginTabIdKey]) {
      // User Login Tab (which has Userport web app) is shut down.

      // Remove listener for user login updates since tab is closed.
      runtime.onMessageExternal.removeListener(handleUserLoginUpdate);

      // Delete login tab key from storage.
      storage.local.remove([loginTabIdKey]);
    } else {
      const tabIdKey = tabId.toString();
      storage.local.get(tabIdKey).then((item) => {
        if (item && tabIdKey in item) {
          // Tab with LinkedIn profile is shut down. Remove any stored lead profile in this tab.
          storage.local.remove([tabIdKey]);
        }
      });
    }
  });
}
