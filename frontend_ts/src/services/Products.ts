import { User as FirebaseUser } from "firebase/auth";
import { apiCall, ListObjectsResponse } from "./Api";
import { UserContext } from "./UserContext";

const PRODUCTS_ENDPOINT = "/products/";

// Product as returned by the backend API.
export interface Product {
  id?: string;
  name: string;
  website?: string;
  description: string;
  icp_description: string;
  persona_role_titles: {
    buyers: string[];
    end_users: string[];
    influencers: string[];
  };
  created_at?: string; // ISO 8601 format date string.
  updated_at?: string; // ISO 8601 format date string.
}

type ListProductsResponse = ListObjectsResponse<Product>;

// Fetch all products.
export const listProducts = async (
  firebaseUser: FirebaseUser | null,
  userContext: UserContext | null
): Promise<Product[]> => {
  return await apiCall<Product[]>(
    firebaseUser,
    userContext,
    async (apiClient) => {
      const response = await apiClient.get<ListProductsResponse>(
        PRODUCTS_ENDPOINT
      );
      return response.data.results;
    }
  );
};

// Add a new product.
export const addProduct = async (
  firebaseUser: FirebaseUser | null,
  userContext: UserContext | null,
  newProduct: Product
): Promise<Product> => {
  return await apiCall<Product>(
    firebaseUser,
    userContext,
    async (apiClient) => {
      const response = await apiClient.post<Product>(
        PRODUCTS_ENDPOINT,
        newProduct
      );
      return response.data;
    }
  );
};
