import { AuthContext } from "@/auth/AuthProvider";
import { apiCall, ListObjectsResponse } from "./Api";
import { EnrichmentStatus } from "./Common";

const ACCOUNTS_ENDPOINT = "/accounts/";
const BULK_CREATE_ACCOUNTS_ENDPOINT = "/accounts/bulk_create/";

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
export const listAccounts = async (
  authContext: AuthContext,
  ids?: string[] // Optional parameter for list of IDs
): Promise<Account[]> => {
  const { userContext } = authContext;
  var params: Record<string, any> = { created_by: userContext!.user.id };

  if (ids && ids.length > 0) {
    // Create a comma-separated string for 'id__in' param
    params["id__in"] = ids.join(",");
  }

  return await apiCall<Account[]>(authContext, async (apiClient) => {
    const response = await apiClient.get<ListAccountsResponse>(
      ACCOUNTS_ENDPOINT,
      { params }
    );
    return response.data.results;
  });
};

// Fetch a single Account with given ID.
export const getAccount = async (
  authContext: AuthContext,
  id: string
): Promise<Account> => {
  const { userContext } = authContext;
  var params: Record<string, any> = {
    created_by: userContext!.user.id,
    id: id,
  };

  return await apiCall<Account>(authContext, async (apiClient) => {
    const response = await apiClient.get<ListAccountsResponse>(
      ACCOUNTS_ENDPOINT,
      { params }
    );
    if (response.data.count != 1) {
      throw new Error(
        `Expected 1 Account, got ${response.data.count} Accounts in results.`
      );
    }
    return response.data.results[0];
  });
};

export interface CreateAccountRequest {
  name: string;
  website: string;
  product: string; // ID of the product accounts are enriched for.
}

// Create Single Account for enrichment.
export const createAccount = async (
  authContext: AuthContext,
  request: CreateAccountRequest
): Promise<Account> => {
  return await apiCall<Account>(authContext, async (apiClient) => {
    const response = await apiClient.post<Account>(ACCOUNTS_ENDPOINT, request);
    return response.data;
  });
};

// Account information request in creation request.
export interface AccountInfo {
  name: string;
  website: string;
}

export interface CreateBulkAccountsRequest {
  product: string; // ID of the product accounts are enriched for.
  accounts: AccountInfo[];
}

interface CreateBulkAccountsResponse {
  message: string;
  account_count: number;
  accounts: Account[];
  enrichment_status: Record<string, any>;
}

// Create Accounts in Bulk for enrichment.
export const createBulkAccounts = async (
  authContext: AuthContext,
  request: CreateBulkAccountsRequest
): Promise<Account[]> => {
  return await apiCall<Account[]>(authContext, async (apiClient) => {
    const response = await apiClient.post<CreateBulkAccountsResponse>(
      BULK_CREATE_ACCOUNTS_ENDPOINT,
      request
    );
    return response.data.accounts;
  });
};
