import { AuthContext } from "@/auth/AuthProvider";
import { apiCall, ListObjectsResponse } from "./Api";
import { EnrichmentStatus } from "./Common";
import { USERPORT_TENANT_ID } from "./Common";

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
  technologies: string[] | null;
  funding_details: FundingDetails | null;
  enrichment_status: EnrichmentStatus;
  enrichment_sources: Record<string, any> | null;
  last_enriched_at: string | null;
  custom_fields: Record<string, any> | null;
  settings: Record<string, any> | null;
  created_at: string;
  updated_at: string;
}

export interface FundingDetails {
  total_funding: {
    amount: number | null;
    currency: string | null;
    as_of_date: string | null;
  };
  funding_rounds: FundingRound[];
}

interface FundingRound {
  series: string | null;
  amount: number | null;
  currency: string | null;
  date: string | null;
  lead_investors: string[];
  other_investors: string[];
  valuation: {
    amount: number | null;
    currency: string | null;
    type: string | null;
  };
}

type ListAccountsResponse = ListObjectsResponse<Account>;

interface ListAccountsRequest {
  page?: number; // Optional parameter for page number to fetch
  ids?: string[]; // Optional parameter for list of IDs to filter
}

// Fetch all accounts for given tenant.
export const listAccounts = async (
  authContext: AuthContext,
  request: ListAccountsRequest
): Promise<ListAccountsResponse> => {
  const { userContext } = authContext;
  if (userContext!.tenant.id === USERPORT_TENANT_ID) {
    // Reroute to internal method.
    return listAccountsWithinTenant(authContext, request);
  }

  var params: Record<string, any> = {
    created_by: userContext!.user.id,
  };

  if (request.page) {
    params["page"] = request.page;
  }

  if (request.ids && request.ids.length > 0) {
    // Create a comma-separated string for 'id__in' param
    params["id__in"] = request.ids.join(",");
  }

  return await apiCall<ListAccountsResponse>(authContext, async (apiClient) => {
    const response = await apiClient.get<ListAccountsResponse>(
      ACCOUNTS_ENDPOINT,
      { params }
    );
    return response.data;
  });
};

// Internal method that should only be used for Userport tenant for dev purposes.
const listAccountsWithinTenant = async (
  authContext: AuthContext,
  request: ListAccountsRequest
): Promise<ListAccountsResponse> => {
  const { userContext } = authContext;
  if (userContext!.tenant.id !== USERPORT_TENANT_ID) {
    throw new Error(`Cannot call internal method to List accounts!`);
  }
  var params: Record<string, any> = {};

  if (request.page) {
    params["page"] = request.page;
  }

  if (request.ids && request.ids.length > 0) {
    // Create a comma-separated string for 'id__in' param
    params["id__in"] = request.ids.join(",");
  }

  return await apiCall<ListAccountsResponse>(authContext, async (apiClient) => {
    const response = await apiClient.get<ListAccountsResponse>(
      ACCOUNTS_ENDPOINT,
      { params }
    );
    return response.data;
  });
};

// Fetch a single Account with given ID.
export const getAccount = async (
  authContext: AuthContext,
  id: string
): Promise<Account> => {
  const { userContext } = authContext;
  if (userContext!.tenant.id === USERPORT_TENANT_ID) {
    // Reroute to internal method.
    return getAccountWithinTenant(authContext, id);
  }
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

// Fetch a single Account within tentant.
// We don't enforce that account has to be created by the user.
export const getAccountWithinTenant = async (
  authContext: AuthContext,
  id: string
): Promise<Account> => {
  const { userContext } = authContext;
  if (userContext!.tenant.id !== USERPORT_TENANT_ID) {
    throw new Error(`Cannot call internal method to Fetch account!`);
  }
  var params: Record<string, any> = {
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
interface AccountInfo {
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
