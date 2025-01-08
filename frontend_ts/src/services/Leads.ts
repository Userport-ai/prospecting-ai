import { AuthContext } from "@/auth/AuthProvider";
import { apiCall, ListObjectsResponse } from "./Api";
import { EnrichmentStatus } from "./Common";

const LEADS_ENDPOINT = "/leads/";

// Lead as returned by the backend API.
export interface Lead {
  id: string;
  account_details: {
    id: string;
    name: string;
    industry: string | null;
  };
  first_name: string | null;
  last_name: string | null;
  enrichment_status: EnrichmentStatus;
  role_tile: string | null;
  linkedin_url: string | null;
  email: string | null;
  phone: string | null;
  custom_fields: Record<string, any> | null;
  score: number | null;
  last_enriched_at: string | null;
  created_at: string;
}

type ListLeadsResponse = ListObjectsResponse<Lead>;

// Fetch all Leads. If Account Id is given, it fetches only leads in the given Account Id.
export const listLeads = async (
  authContext: AuthContext,
  accountId: string | null
): Promise<Lead[]> => {
  var params: Record<string, any> = {};
  if (accountId) {
    params["account__id"] = accountId;
  }
  return await apiCall<Lead[]>(authContext, async (apiClient) => {
    const response = await apiClient.get<ListLeadsResponse>(LEADS_ENDPOINT, {
      params,
    });
    return response.data.results;
  });
};
