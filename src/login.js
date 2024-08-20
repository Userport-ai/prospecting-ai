import "./login.css";
import { useContext, useEffect } from "react";
import firebase from "firebase/compat/app";
import * as firebaseui from "firebaseui";
import "firebaseui/dist/firebaseui.css";
import { AuthContext } from "./root";
import { redirect } from "react-router-dom";
import { Layout } from "antd";

const { Header, Content } = Layout;

export const loginLoader = (authContext) => {
  return async () => {
    if (authContext.user) {
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
          // Do not redirect. The login page in the app will automatically redirect.
          // The authResult contains user object but we don't need it because we also listen
          // to the onAuthStateChanged event to fetch User object whenever there is a sign in or
          // sign out event.
          // One example of information you cannot find other places is new user.
          return false;
        },
        signInFailure: function (error) {
          // Throw error so we understand what happened.
          console.log("failed to sign in user with error: ", error);
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
          <h1 id="company-title">Userport</h1>
          <h3 id="company-tag-line">Personalize Outreach using AI</h3>
          <p id="login-or-signup-text">Login or Sign Up</p>
          <div id="firebase-auth-container"></div>
        </div>
      </Content>
    </>
  );
}

export default Login;
