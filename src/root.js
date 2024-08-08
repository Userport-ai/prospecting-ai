import { initializeApp } from "firebase/app";
import {
  getAuth,
  onAuthStateChanged,
  signOut,
  sendEmailVerification,
} from "firebase/auth";
import { createContext, useEffect, useState } from "react";
import { redirect } from "react-router-dom";

export const AuthContext = createContext(null);

// Configures Firebase, checks if user is logged in and provides auth values.
function Root({ children }) {
  // Your web app's Firebase configuration
  // For Firebase JS SDK v7.20.0 and later, measurementId is optional
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
  const auth = getAuth(app);

  const [user, setUser] = useState(null);
  const [isAuthLoading, setIsAuthLoading] = useState(true);

  // Observe auth object for changes in user's signed in state.
  useEffect(() => {
    const unRegistered = onAuthStateChanged(auth, (authUser) => {
      setUser(authUser);
      setIsAuthLoading(false);
      if (authUser) {
        if (!authUser.emailVerified) {
          // Ask user to verify email.
          sendEmailVerification(authUser);
        }
      } else {
        // Redirect to login page.
        return redirect("/login");
      }
    });
    return () => unRegistered();
  }, [auth]);

  // Callback for User Logout event.
  async function handleLogout() {
    try {
      await signOut(auth);
    } catch (error) {
      throw error;
    }
  }

  const value = {
    user,
    isAuthLoading,
    auth,
    handleLogout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export default Root;
