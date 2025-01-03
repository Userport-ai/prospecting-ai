import { User as FirebaseUser } from "firebase/auth";
import axios from "axios";

// User Context as returned by the backend API.
export interface UserContext {
  user: {
    id: string;
    email: string;
    role: string;
    first_name: string | null;
    last_name: string | null;
    full_name: string | null;
  };
  tenant: {
    id: string;
    name: string;
    website: string;
    status: string;
  };
  config: Record<string, any>;
  settings: Record<string, any>;
}

// Fetch context from the backend for the given user.
export const fetchUserContext = async (user: FirebaseUser) => {
  try {
    const idToken = await user.getIdToken();
    const response = await axios.get(
      `${import.meta.env.VITE_API_HOSTNAME}/api/v2/context`,
      {
        headers: {
          Authorization: `Bearer ${idToken}`,
        },
      }
    );
    const userContext: UserContext = response.data;
    return userContext;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response) {
      if (error.response.headers["content-type"] === "application/json") {
        // Convert JSON from error response back to string.
        const errorMessage = `${error.message}: ${JSON.stringify(
          error.response.data
        )}`;
        throw new Error(errorMessage);
      }
      // The error message will always contain the status code.
      var errorMessage: string = `${error.message}: `;
      if (error.response.headers["content-type"] === "application/json") {
        errorMessage += JSON.stringify(error.response.data);
      } else {
        errorMessage += error.response.data;
      }
      throw new Error(errorMessage);
    } else {
      throw error;
    }
  }
};
