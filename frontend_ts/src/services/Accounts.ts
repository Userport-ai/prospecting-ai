import { AuthContext } from "@/auth/AuthProvider";
import { apiCall, ListObjectsResponse } from "./Api";
import { EnrichmentStatus } from "./Common";

const ACCOUNTS_ENDPOINT = "/accounts/";

// Account as returned by the backend API.
export interface Account {
  id: string;
  product: string; // ID of the Product associated with the account.
  name: string;
  website: string | null;
  linkedin_url: string | null;
  industry: string | null;
  location: string | null;
  employee_count: number | null;
  company_type: string | null;
  founded_year: number | null;
  customers: string[] | null;
  competitors: string[] | null;
  technologies: Record<string, any> | null;
  funding_details: Record<string, any> | null;
  enrichment_status: EnrichmentStatus;
  enrichment_sources: Record<string, any> | null;
  last_enriched_at: string | null;
  custom_fields: Record<string, any> | null;
  settings: Record<string, any> | null;
  created_at: string;
}

type ListAccountsResponse = ListObjectsResponse<Account>;

// Fetch all accounts for given tenant.
// TODO: Update this to only fetch accounts created by given user.
export const listAccounts = async (
  authContext: AuthContext
): Promise<Account[]> => {
  return await apiCall<Account[]>(authContext, async (apiClient) => {
    const response = await apiClient.get<ListAccountsResponse>(
      ACCOUNTS_ENDPOINT
    );
    return response.data.results;
  });
};

export interface CreateAccountsRequest {
  product: string; // ID of the product accounts are enriched for.
  accounts: { name: string }[];
}

interface CreateAccountsResponse {
  message: string;
  account_count: number;
  accounts: Account[];
  enrichment_status: Record<string, any>;
}

// Create Accounts for enrichment.
export const createAccounts = async (
  authContext: AuthContext,
  request: CreateAccountsRequest
): Promise<Account[]> => {
  return await apiCall<Account[]>(authContext, async (apiClient) => {
    const response = await apiClient.post<CreateAccountsResponse>(
      ACCOUNTS_ENDPOINT,
      request
    );
    return response.data.accounts;
  });
};
