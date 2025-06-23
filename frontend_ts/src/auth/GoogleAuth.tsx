import { GoogleAuthProvider, signInWithPopup } from "firebase/auth";
import { auth } from "./BaseAuth";

// Method to handle Google Sign In.
export async function handleGoogleSignIn() {
  try {
    const provider = new GoogleAuthProvider();
    // const result = await signInWithRedirect(auth, provider);
    await signInWithPopup(auth, provider);
  } catch (error) {
    // Handle errors (e.g., display an error message)
    console.error("Error signing in with Google:", error);
  }
}
