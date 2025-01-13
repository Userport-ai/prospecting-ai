// Common interfaces.

export enum LinkedInActivityParsingResult {
  SCHEDULED = "scheduled", // Scheduled status only exists on web app (per design).
  IN_PROGRESS = "in_progress",
  COMPLETE = "complete",
  FAILED = "failed",
}

enum RequestType {
  START_ACTIVITY_PARSING = "start_activity_parsing",
  GET_ACTIVITY_PARSING_RESULT = "get_activity_parsing_result",
}

interface BaseRequest {
  request_type: RequestType;
}

enum ResponseType {
  SUCCESS = "success",
  ERROR = "error",
}

interface BaseResponse {
  type: ResponseType;
}

interface ErrorResponse extends BaseResponse {
  error_message: string;
}

// Interfaces specific to each API.

interface StartActivityParsingRequst extends BaseRequest {
  linkedin_url: string;
}

interface StartActivityParsingResponse extends BaseResponse {
  tab_id: number; // ID of the tab where activity parsing is taking place.
  status: LinkedInActivityParsingResult;
}

interface GetActivityParsingResultRequest extends BaseRequest {
  tab_id: number;
  linkedin_url: string;
}

interface GetActivityParsingResultResponse extends BaseResponse {
  status: LinkedInActivityParsingResult;
  parsed_data: {
    posts_html?: string | null;
    comments_html?: string | null;
    reactions_html?: string | null;
  };
}

const activityParserExtensionId = import.meta.env
  .VITE_ACTIVITY_PARSER_EXTENSION_ID;

// Start LinkedIn Activity Parsing for given URL.
// Reference: https://developer.chrome.com/docs/extensions/develop/concepts/messaging#external.
export const startLinkedInActivityParsing = async (
  linkedInUrl: string
): Promise<StartActivityParsingResponse> => {
  validateExtensionExists();

  const request: StartActivityParsingRequst = {
    request_type: RequestType.START_ACTIVITY_PARSING,
    linkedin_url: linkedInUrl,
  };

  const response: BaseResponse = await chrome.runtime.sendMessage(
    activityParserExtensionId,
    request
  );

  if (response.type === ResponseType.ERROR) {
    throw new Error((response as ErrorResponse).error_message);
  }

  return response as StartActivityParsingResponse;
};

// Returns current linkedin activity parsing status and result.
// If the parsing is still in progress, result with be empty.
export const getLinkedInActivityParsingResult = async (
  tabId: number,
  linkedinUrl: string
): Promise<GetActivityParsingResultResponse> => {
  validateExtensionExists();

  const request: GetActivityParsingResultRequest = {
    request_type: RequestType.GET_ACTIVITY_PARSING_RESULT,
    tab_id: tabId,
    linkedin_url: linkedinUrl,
  };

  const response: BaseResponse = await chrome.runtime.sendMessage(
    activityParserExtensionId,
    request
  );

  if (response.type === ResponseType.ERROR) {
    throw new Error((response as ErrorResponse).error_message);
  }

  return response as GetActivityParsingResultResponse;
};

const validateExtensionExists = () => {
  if (!chrome || !chrome.runtime) {
    throw new Error(
      "Chrome extension is not installed, please install it from the Chrome Web Store!"
    );
  }
};
