import { runtime, tabs, storage } from "webextension-polyfill";
import { signOut, signInWithCustomToken } from "firebase/auth/web-extension";
import { getAuthObj } from "./auth";
// No external code loading possible (this disables all extensions such as Replay, Surveys, Exceptions etc.)
// Reference: https://posthog.com/docs/libraries/js.
import posthog from "posthog-js/dist/module.no-external";

// Module constants.
// Login process is global (per window not tab) and so the state associated
// with the process is stored as a global key instead of per tab.
const loginTabIdKey = "login-tab-id";
const webAppTab = "web-app-tab";
const extensionTab = "extension-tab";

// Handle login request. Open userport in a new tab and log them in.
export function startLogin(request) {
  // Send event.
  posthog.capture("extension_login_btn_clicked");

  // Remove existing listeners listening to login if any.
  runtime.onMessageExternal.removeListener(handleUserLoginUpdate);

  tabs
    .create({
      url: `${process.env.REACT_APP_HOSTNAME}/login?source=extension`,
      active: true,
    })
    .then((tab) => {
      // Store tab ID of web app and extension for login. Delete it when tab is closed or login is complete.
      storage.local
        .set({
          [loginTabIdKey]: { webAppTab: tab.id, extensionTab: request.tabId },
        })
        .then(() => {
          // Add listener to listen to updates of user login from the Userport web app.
          runtime.onMessageExternal.addListener(handleUserLoginUpdate);
        });
    });
}

// Handle messages related to user login from Userport login page in the Web App.
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
    signInWithCustomToken(getAuthObj(), request.token)
      .then((userCredential) => {
        const loggedInUser = userCredential.user;
        console.log("user logged in successfully: ", loggedInUser.email);
      })
      .finally(() => {
        // Close the web app Login tab and switch extension tab to active. Cleaning up storage state will be done in close tab handler.
        storage.local.get([loginTabIdKey]).then((item) => {
          const webAppTabId = item[loginTabIdKey].webAppTab;
          const extensionTabId = item[loginTabIdKey].extensionTab;
          tabs.update(extensionTabId, { active: true });
          // Tab reload is needed so that we can check if report exists on server now that user is logged in.
          tabs.reload(extensionTabId);
          tabs.remove(webAppTabId);
        });
      });

    return sendResponse();
  }

  throw Error(`Unidentified event request: ${request}`);
}

// Handle tab closed event when user is logging in.
// Depending on which tab is closed, we clear login state (signalling end of login)
// or we don't do anything. Returns true if login state was cleaned up and false otherwise.
export async function handleLoginTabClosed(tabId) {
  return storage.local.get([loginTabIdKey]).then((item) => {
    if (loginTabIdKey in item && tabId === item[loginTabIdKey].webAppTab) {
      // User Login Tab on Userport Web App has been closed.

      // Remove listener for user login updates since tab is closed.
      runtime.onMessageExternal.removeListener(handleUserLoginUpdate);

      // Delete login tab key from storage.
      storage.local.remove([loginTabIdKey]);
      return true;
    }
    return false;
  });
}

// Logs out user. Async method that returns a promise.
export function logOut() {
  return signOut(getAuthObj());
}
