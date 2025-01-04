import { User as FirebaseUser } from "firebase/auth";
import axios from "axios";
import { handleAPIError } from "./Api";

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
    handleAPIError(error);
    throw new Error("This line is unreachable but ensures strict typing.");
  }
};
