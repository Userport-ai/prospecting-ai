import { runtime, tabs, storage } from "webextension-polyfill";
import { signOut, signInWithCustomToken } from "firebase/auth/web-extension";
import { getAuthObj } from "./auth";
import { captureEvent } from "./metrics";

// Module constants.
// Login process is global (per window not tab) and so the state associated
// with the process is stored as a global key instead of per tab.
const loginTabIdKey = "login-tab-id";
const webAppTab = "web-app-tab";
const extensionTab = "extension-tab";

// Handle login request. Open userport in a new tab and log them in.
export function startLogin(request) {
  // Send event.
  captureEvent("extension_login_btn_clicked");

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
    getAuthObj().then((auth) => {
      signInWithCustomToken(auth, request.token)
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
    });

    return sendResponse();
  }

  throw Error(`Unidentified event request: ${request}`);
}

// Returns true if user is currently trying to login on given tab Id and false otherwise.
export async function isUserLoggingIn(tabId) {
  const item = await storage.local.get([loginTabIdKey]);
  return loginTabIdKey in item && tabId == item[loginTabIdKey].webAppTab;
}

// Handle Login tab closed event (Userport web app tab closure) after user has logged in.
// Assume that check for whether user is loggin in has already been done.
// Method clears login state (signalling end of login) from storage.
export function handleLoginTabClosed() {
  // Remove listener for user login updates since tab is closed.
  runtime.onMessageExternal.removeListener(handleUserLoginUpdate);

  // Delete login tab key from storage.
  storage.local.remove([loginTabIdKey]);

  console.log("done with cleanup login");
}

// Logs out user. Async method that returns a promise.
export async function logOut() {
  const auth = await getAuthObj();
  return signOut(auth);
}
