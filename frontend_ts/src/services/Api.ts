import { User as FirebaseUser } from "firebase/auth";
import axios, { AxiosInstance } from "axios";
import { UserContext } from "./UserContext";

// Create Axios API instance that will be used for all outbound
// APIs to the backend.
export const createAPI = (
  firebaseUser: FirebaseUser,
  userContext: UserContext
) => {
  const api = axios.create({
    baseURL: import.meta.env.VITE_API_HOSTNAME,
  });

  // Add a request interceptor to include the Firebase ID token
  api.interceptors.request.use(
    async (config) => {
      // Set Authorization header.
      const token = await firebaseUser.getIdToken();
      config.headers.Authorization = `Bearer ${token}`;

      // Set Tenant ID.
      const tenantId = userContext.tenant.id;
      config.headers["X-Tenant-Id"] = tenantId;

      return config;
    },
    (error) => {
      return Promise.reject(error);
    }
  );

  return api;
};

// Common method to handle errors thrown in API calls.
// If there is JSON payload in the response, it will be extracted
// and thrown as part of the final error object.
// This method should always throw an error.
export const handleAPIError = (error: any) => {
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
};

// Method signature for clients to implement business logic in the API calls.
interface ClientMethod<T> {
  (apiClient: AxiosInstance): Promise<T>;
}

// Simple scaffolding around API call to ensure clients can just write the business logic and leave
// creating API client and handling error to it.
export const apiCall = async <T>(
  firebaseUser: FirebaseUser | null,
  userContext: UserContext | null,
  clientMethod: ClientMethod<T>
) => {
  try {
    if (!firebaseUser || !userContext) {
      throw Error("Missing credentials for making an API call.");
    }
    const apiClient = createAPI(firebaseUser, userContext);
    const result = await clientMethod(apiClient);
    return result;
  } catch (error) {
    handleAPIError(error);
    throw new Error("This line is unreachable but ensures strict typing.");
  }
};
