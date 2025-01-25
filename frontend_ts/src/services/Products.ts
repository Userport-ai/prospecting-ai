import { apiCall, checkDeletionSuccessful, ListObjectsResponse } from "./Api";
import { AuthContext } from "@/auth/AuthProvider";

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

// Fetch all products within a tenant.
export const listProducts = async (
  authContext: AuthContext
): Promise<Product[]> => {
  return await apiCall<Product[]>(authContext, async (apiClient) => {
    const response = await apiClient.get<ListProductsResponse>(
      PRODUCTS_ENDPOINT
    );
    return response.data.results;
  });
};

// Add a new product.
export const addProduct = async (
  authContext: AuthContext,
  newProduct: Product
): Promise<Product> => {
  return await apiCall<Product>(authContext, async (apiClient) => {
    const response = await apiClient.post<Product>(
      PRODUCTS_ENDPOINT,
      newProduct
    );
    return response.data;
  });
};

// Fetch all products.
export const deleteProduct = async (
  authContext: AuthContext,
  id: string
): Promise<void> => {
  return await apiCall<void>(authContext, async (apiClient) => {
    const response = await apiClient.delete(`${PRODUCTS_ENDPOINT}${id}/`);
    checkDeletionSuccessful(response);
  });
};
