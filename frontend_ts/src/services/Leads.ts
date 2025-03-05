import { AuthContext } from "@/auth/AuthProvider";
import { apiCall, ListObjectsResponse } from "./Api";
import { EnrichmentStatus } from "./Common";
import { ParsedHTML } from "./Extension";

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

interface CustomFields {
  evaluation: Evaluation;
  personality_insights: PersonalityInsights;
  [key: string]: any;
}

interface Evaluation {
  fit_score: number;
  persona_match: string;
  matching_criteria?: string[];
  matching_signals?: string[];
  recommended_approach: string;
  overall_analysis: string[];
  rationale: string[];
}

interface PersonalityInsights {
  traits: PersonalityTrait;
  engaged_products: string[];
  areas_of_interest: AreaOfInterest[];
  engaged_colleagues: string[];
  recommended_approach: RecommendedApproach;
  personalization_signals: PersonalizationSignal[];
}

export interface PersonalityTrait {
  evidence: string[];
  description: string;
}

export interface AreaOfInterest {
  description: string;
  supporting_activities: string[];
}

export interface RecommendedApproach {
  approach: string;
  cautions: string[];
  key_topics: string[];
  best_channels: string[];
  timing_preferences: string;
  conversation_starters: string[];
}

export interface PersonalizationSignal {
  description: string;
  reason: string;
  outreach_message: string;
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

type ListLeadsResponse = ListObjectsResponse<Lead>;

// Fetch all Leads. If Account Id is given, it fetches only leads in the given Account Id.
export const listLeads = async (
  authContext: AuthContext,
  accountId?: string
): Promise<ListLeadsResponse> => {
  return listLeadsHelper(authContext, 1, accountId);
};

// Fetch suggested leads for the given account.
export const listSuggestedLeads = async (
  authContext: AuthContext,
  page: number,
  accountId?: string
): Promise<ListLeadsResponse> => {
  return listLeadsHelper(
    authContext,
    page,
    accountId,
    SuggestionStatus.SUGGESTED
  );
};

// Approve given Lead.
export const approveLead = async (
  authContext: AuthContext,
  id: string
): Promise<Lead> => {
  const request = { suggestion_status: SuggestionStatus.APPROVED };
  const endpoint = `${LEADS_ENDPOINT}${id}/`;
  return await apiCall<Lead>(authContext, async (apiClient) => {
    const response = await apiClient.patch<Lead>(endpoint, request);
    return response.data;
  });
};

export const enrichLinkedInActivity = async (
  authContext: AuthContext,
  id: string,
  parsedHTML: ParsedHTML
): Promise<void> => {
  const endpoint = `${LEADS_ENDPOINT}${id}/enrich_linkedin_activity/`;
  return await apiCall<void>(authContext, async (apiClient) => {
    await apiClient.post(endpoint, parsedHTML);
  });
};

// Helper to list leads.
const listLeadsHelper = async (
  authContext: AuthContext,
  page: number,
  accountId?: string,
  suggestionStatus?: SuggestionStatus
): Promise<ListLeadsResponse> => {
  var params: Record<string, any> = { page: page };
  if (accountId) {
    params["account"] = accountId;
  }
  if (suggestionStatus) {
    params["suggestion_status"] = SuggestionStatus.SUGGESTED;
  } else {
    // Only list approved leads by default.
    params["suggestion_status"] = SuggestionStatus.APPROVED;
  }
  return await apiCall<ListLeadsResponse>(authContext, async (apiClient) => {
    const response = await apiClient.get<ListLeadsResponse>(LEADS_ENDPOINT, {
      params,
    });
    return response.data;
  });
};
