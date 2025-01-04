import { User as FirebaseUser } from "firebase/auth";
import { apiCall } from "./Api";
import { UserContext } from "./UserContext";

// Product as returned by the backend API.
export interface Product {
  id: string;
  name: string;
  website?: string;
  description: string;
  icp_description: string;
  persona_role_titles: {
    roles: string[];
  };
  created_at: string; // ISO 8601 format date string.
  updated_at: string; // ISO 8601 format date string.
  created_by: string; // ID of the creator.
}

// Fetch all products.
export const fetchProducts = async (
  firebaseUser: FirebaseUser | null,
  userContext: UserContext | null
): Promise<Product[]> => {
  return await apiCall(firebaseUser, userContext, async (apiClient) => {
    const response = await apiClient.get("/products");
    const products: Product[] = response.data;
    return products;
  });
};
