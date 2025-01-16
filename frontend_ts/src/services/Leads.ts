import { AuthContext } from "@/auth/AuthProvider";
import { apiCall, ListObjectsResponse } from "./Api";
import { EnrichmentStatus } from "./Common";

const LEADS_ENDPOINT = "/leads/";

// Lead Enrichment data as defined in
// https://github.com/Userport-ai/prospecting-ai/blob/sowrabh/v2/api/django_app/app/apis/accounts/enrichment_callback.py.
interface EnrichmentData {
  // Profile metadata
  profile_url: string;
  public_identifier: string;
  profile_pic_url: string;
  headline: string;
  location: string;

  // Professional details
  occupation: string;
  summary: string;
  follower_count: number;
  connection_count: number;

  // Career and experience
  companies_count: string;
  industry_exposure: string[];
  total_years_experience: number;
  previous_roles: string[];

  // Current role details.
  current_role: {
    title: string;
    company: string;
    department: string;
    seniority: string;
    years_in_role: number | null;
    description: string | null;
    location: string | null;
    start_date: string | null;
  };

  // Skills and education
  skills: string[];
  certifications: string[];
  education: string[];
  languages: string[];

  // Additional content
  recommendations: string[];

  // Location details
  country: string;
  country_full_name: string;
  city: string;
  state: string;

  // Source tracking
  data_source: string;

  // Timestamp
  enriched_at: string;
}

interface Evaluation {
  fit_score: number;
  persona_match: string;
  matching_criteria: string[];
  recommended_approach: string[];
  analysis: string[];
  rationale: string[];
}

interface CustomFields {
  evaluation: Evaluation;
  [key: string]: any;
}

enum Source {
  MANUAL = "manual",
  ENRICHMENT = "enrichment",
  IMPORT = "import",
}

enum SuggestionStatus {
  SUGGESTED = "suggested",
  APPROVED = "approved",
  REJECTED = "rejected",
  MANUAL = "manual",
}

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
  role_title: string | null;
  linkedin_url: string;
  email: string | null;
  phone: string | null;
  custom_fields: CustomFields | null;
  enrichment_data: EnrichmentData;
  source: Source;
  suggestion_status: SuggestionStatus;
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
  return listLeadsHelper(authContext, accountId);
};

// Fetch suggested leads for the given account.
export const listSuggestedLeads = async (
  authContext: AuthContext,
  accountId: string | null
): Promise<Lead[]> => {
  return listLeadsHelper(authContext, accountId, SuggestionStatus.SUGGESTED);
};

// Helper to list leads.
const listLeadsHelper = async (
  authContext: AuthContext,
  accountId: string | null,
  suggestionStatus?: SuggestionStatus
): Promise<Lead[]> => {
  var params: Record<string, any> = {};
  if (accountId) {
    params["account__id"] = accountId;
  }
  if (suggestionStatus) {
    params["suggestion_status"] = SuggestionStatus.SUGGESTED;
  } else {
    // Only list approved leads by default.
    params["suggestion_status"] = SuggestionStatus.APPROVED;
  }
  return await apiCall<Lead[]>(authContext, async (apiClient) => {
    const response = await apiClient.get<ListLeadsResponse>(LEADS_ENDPOINT, {
      params,
    });
    return response.data.results;
  });
};
