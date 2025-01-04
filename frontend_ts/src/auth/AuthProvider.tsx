import React, { createContext, useContext, ReactNode } from "react";
import { auth } from "./BaseAuth";
import { useState, useEffect } from "react";
import { onAuthStateChanged, User as FirebaseUser } from "firebase/auth";
import { signOut } from "firebase/auth";
import { fetchUserContext, UserContext } from "@/services/UserContext";

// Define Context that will be provided to children nodes.
export interface AuthContext {
  firebaseUser: FirebaseUser | null;
  userContext: UserContext | null;
}

const AuthContext = createContext<AuthContext>({
  firebaseUser: null,
  userContext: null,
});

export const useAuthContext = () => {
  return useContext(AuthContext);
};

interface AuthProviderProps {
  children: ReactNode;
}

const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [firebaseUser, setFirebaseUser] = useState<FirebaseUser | null>(null);
  const [userContext, setUserContext] = useState<UserContext | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    // Firebase listener for change in auth status.
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      setFirebaseUser(user);
      if (!user) {
        // User is logged out.
        setUserContext(null);
        setLoading(false);
      }

      // Fetch user context.
      fetchUserContext(user!)
        .then((userContext) => setUserContext(userContext))
        .catch((error) =>
          setError(new Error(`Failed to fetch user context: ${error.message}`))
        )
        .finally(() => setLoading(false));
    });

    return () => unsubscribe();
  }, []);

  if (loading) {
    // Auth is loading, do nothing.
    return <div></div>;
  }

  if (error) {
    // Rethrow error to be caught by ErrorBoundary.
    throw error;
  }

  return (
    <AuthContext.Provider
      value={{ firebaseUser: firebaseUser, userContext: userContext }}
    >
      {children}
    </AuthContext.Provider>
  );
};

// Handles user logout, there is no need to navigate
// to login since App will automatically check new value of user
// and redirect to login.
export const handleLogout = async () => {
  try {
    await signOut(auth);
  } catch (error) {
    console.error("Logout Error:", error);
    throw error;
  }
};

export default AuthProvider;
