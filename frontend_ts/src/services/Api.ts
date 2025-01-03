import { User as FirebaseUser } from "firebase/auth";
import axios from "axios";
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
