// src/services/CustomColumns.ts - Extended with generation function
import { AuthContext } from "@/auth/AuthProvider";
import { apiCall } from "./Api";

const BASE_ENDPOINT = "/custom_columns/";

// Interface matching the structure needed for the POST request
export interface CreateCustomColumnRequest {
  name: string;
  description?: string | null;
  question: string;
  entity_type: "account" | "lead";
  response_type: "string" | "json_object" | "boolean" | "number" | "enum";
  response_config?: {
    allowed_values?: string[];
    // Add other potential config fields based on your backend documentation if needed
    // e.g., max_length, format, tone for string
    // e.g., min, max, decimal_places, unit for number
    // e.g., true_label, false_label for boolean
  } | null;
  ai_config: {
    model: string; // e.g., 'gemini-pro'
    temperature: number; // e.g., 0.1
    use_internet: boolean;
    unstructured_response: boolean;
    use_linkedin_activity: boolean;
  };
  context_type: string[]; // e.g., ['company_profile']
  refresh_interval?: number | null; // In hours
  is_active?: boolean;
}

// Interface representing the created custom column (adjust based on actual API response)
export interface CustomColumn extends CreateCustomColumnRequest {
  id: string; // UUID assigned by backend
  created_by: string;
  created_at: string; // ISO Date string
  updated_at: string; // ISO Date string
  // Potentially add last_refresh if returned
}

// Response for the generate values API call
export interface GenerateValuesResponse {
  message: string;
  job_id: string;
  entity_count: number;
  request_id: string;
}

// Function to create a new custom column
export const createCustomColumn = async (
  authContext: AuthContext,
  columnData: CreateCustomColumnRequest
): Promise<CustomColumn> => {
  return await apiCall<CustomColumn>(authContext, async (apiClient) => {
    // Clean up potentially empty/null optional fields if needed by backend
    const payload: Partial<CreateCustomColumnRequest> = { ...columnData };
    if (!payload.description) delete payload.description;
    if (
      !payload.response_config ||
      Object.keys(payload.response_config).length === 0
    ) {
      delete payload.response_config;
    } else if (
      payload.response_type !== "enum" &&
      payload.response_config?.allowed_values
    ) {
      // Clean up allowed_values if type is not enum
      delete payload.response_config.allowed_values;
      if (Object.keys(payload.response_config).length === 0) {
        delete payload.response_config;
      }
    }
    if (
      payload.refresh_interval === null ||
      payload.refresh_interval === undefined
    )
      delete payload.refresh_interval;
    if (payload.is_active === undefined) delete payload.is_active; // Keep default handling if undefined

    const response = await apiClient.post<CustomColumn>(BASE_ENDPOINT, payload);
    return response.data;
  });
};

// Get Custom Column with given ID.
export const getCustomColumn = async (
  authContext: AuthContext,
  columnId: string
): Promise<CustomColumn> => {
  return await apiCall<CustomColumn>(authContext, async (apiClient) => {
    const response = await apiClient.get<CustomColumn>(
      `${BASE_ENDPOINT}${columnId}/`
    );
    return response.data;
  });
};

// Function to trigger the generation of custom column values
export const generateCustomColumnValues = async (
  authContext: AuthContext,
  columnId: string,
  entityIds: string[]
): Promise<GenerateValuesResponse> => {
  if (!columnId || columnId === "undefined") {
    throw new Error(
      "Invalid column ID. Cannot trigger generation without a valid column ID."
    );
  }

  if (!entityIds || entityIds.length === 0) {
    throw new Error(
      "No entity IDs provided. Cannot trigger generation without entities."
    );
  }

  return await apiCall<GenerateValuesResponse>(
    authContext,
    async (apiClient) => {
      console.log(
        `Generating values for column ${columnId} and entities:`,
        entityIds
      );

      try {
        const response = await apiClient.post<GenerateValuesResponse>(
          `${BASE_ENDPOINT}${columnId}/generate_values/`,
          { entity_ids: entityIds }
        );
        return response.data;
      } catch (error: any) {
        console.error("Error generating custom column values:", error);
        // Enhance error message with more details
        const errorMessage =
          error.response?.data?.error || error.message || "Unknown error";
        throw new Error(`Failed to generate column values: ${errorMessage}`);
      }
    }
  );
};

// Add functions for list, get, update, delete custom columns here later if needed
// export const listCustomColumns = async (...) => {};
// export const getCustomColumn = async (...) => {};
// export const updateCustomColumn = async (...) => {};
// export const deleteCustomColumn = async (...) => {};

export interface CustomColumnValueData {
  name: string;
  description: string | null;
  question: string | null;
  value: string | number | boolean | object | null; // The actual AI-generated value
  confidence: number | null;
  rationale: string | null;
  generated_at: string; // ISO date string
  response_type: "string" | "json_object" | "boolean" | "number" | "enum";
  columnId: string; // ID of the custom column this value belongs to - REQUIRED
  status?: "pending" | "processing" | "completed" | "error"; // Status of the generation
}
