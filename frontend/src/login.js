/*global chrome*/
import "./login.css";
import { useContext, useEffect } from "react";
import firebase from "firebase/compat/app";
import * as firebaseui from "firebaseui";
import "firebaseui/dist/firebaseui.css";
import { AuthContext } from "./root";
import { redirect } from "react-router-dom";
import { Layout } from "antd";
import {
  getChromeExtensionQueryParamsString,
  isCalledFromChromeExtension,
} from "./helper-functions";

const { Header, Content } = Layout;

// Send data to chrome extension. Data can be any JSON object.
async function sendDataToChromeExtension(data) {
  await chrome.runtime.sendMessage(
    process.env.REACT_APP_CHROME_EXTENSION_ID,
    data
  );
  if (chrome.runtime.lastError) {
    // Error in connecting to chrome extension.
    throw chrome.runtime.lastError;
  }
}

// Fetch Custom Auth for given logged in user from the server.
async function fetch_auth_custom_token(user) {
  const idToken = await user.getIdToken();
  const response = await fetch("/api/v1/auth/custom-token", {
    headers: { Authorization: "Bearer " + idToken },
  });
  const result = await response.json();
  if (result.status === "error") {
    throw result;
  }
  return result.custom_token;
}

export const loginLoader = (authContext) => {
  return async () => {
    // If user is logging in from chrome extension.
    const loginFromChromeExtension = isCalledFromChromeExtension();
    if (loginFromChromeExtension) {
      // Send a message to ensure that chrome extension actually opened this view.
      await sendDataToChromeExtension({ event: "ping" });
    }

    const user = authContext.user;
    if (user) {
      if (loginFromChromeExtension) {
        // We need to fetch custom auth token from the server and send it to the extension.
        const custom_token = await fetch_auth_custom_token(user);
        await sendDataToChromeExtension({
          event: "logged-in",
          token: custom_token,
        });

        // Add chrome extension query params to logged in page.
        return redirect(`/logged-in?${getChromeExtensionQueryParamsString()}`);
      }

      // User already logged in, redirect to logged in page.
      return redirect("/logged-in");
    }
    return null;
  };
};

function Login() {
  const { auth } = useContext(AuthContext);

  useEffect(() => {
    // This will mount the Firebase Sign In UI and allow user to sign in using given options.
    var uiConfig = {
      callbacks: {
        // Called when the user has been successfully signed in.
        signInSuccessWithAuthResult: function (authResult, redirectUrl) {
          // Do not redirect. This page will reload and it will automatically redirect since user will now be signed in.
          // The authResult contains user object but we don't need it because we also listen
          // to the onAuthStateChanged event to fetch User object whenever there is a sign in or
          // sign out event.
          // One example of information you cannot find other places is new user.
          return false;
        },
        signInFailure: function (error) {
          // Throw error so we understand what happened.
          throw error;
        },
      },
      // Sign In flow does not seem to work on localhost if not used in popup mode, don't know why.
      signInFlow: "popup",
      signInOptions: [
        firebase.auth.EmailAuthProvider.PROVIDER_ID,
        firebase.auth.GoogleAuthProvider.PROVIDER_ID,
      ],
      // TODO: Change this.
      tosUrl: "https://www.example.com/terms-conditions",
      privacyPolicyUrl: function () {
        // TODO: Change this.
        window.location.assign("https://www.example.com/privacy-policy");
      },
    };
    const ui =
      firebaseui.auth.AuthUI.getInstance() || new firebaseui.auth.AuthUI(auth);
    ui.start("#firebase-auth-container", uiConfig);
  }, [auth]);

  return (
    <>
      <Header id="login-header"></Header>
      <Content id="login-content">
        <div id="login-content-container">
          <div id="company-logo-container">
            <img
              src="/combination_mark_primary.png"
              alt="userport-combination-mark"
            />
          </div>
          <h3 id="company-tag-line">Personalize Outreach using AI</h3>
          <p id="login-or-signup-text">Login or Sign Up</p>
          <div id="firebase-auth-container"></div>
        </div>
      </Content>
    </>
  );
}

export default Login;
