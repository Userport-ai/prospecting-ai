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
      // User already logged in, redirect to leads page.
      return redirect("/leads");
    }
    return null;
  };
};

function Login() {
  const { auth } = useContext(AuthContext);

  useEffect(() => {
    // This will mount the Firebase Sign In UI and allow user to sign in using given options.
    var uiConfig = {
      signInOptions: [
        firebase.auth.EmailAuthProvider.PROVIDER_ID,
        firebase.auth.GoogleAuthProvider.PROVIDER_ID,
      ],
      signInSuccessUrl: "/leads",
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
          <h1 id="company-title">Userport.ai</h1>
          <p id="login-or-signup-text">Login or Sign Up</p>
          <div id="firebase-auth-container"></div>
        </div>
      </Content>
    </>
  );
}

export default Login;
