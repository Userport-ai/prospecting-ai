import { useContext, useEffect } from "react";
import firebase from "firebase/compat/app";
import * as firebaseui from "firebaseui";
import "firebaseui/dist/firebaseui.css";
import { AuthContext } from "./root";
import { Navigate } from "react-router-dom";

function Login() {
  const { user, auth } = useContext(AuthContext);

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

  if (user) {
    return <Navigate to="/leads" replace />;
  }

  return (
    <>
      <h1>LOGIN</h1>
      <div id="firebase-auth-container"></div>
    </>
  );
}

export default Login;
