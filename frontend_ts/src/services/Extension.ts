// Common interfaces.

export enum LinkedInActivityParsingStatus {
  SCHEDULED = "scheduled", // Scheduled status only exists on web app (per design).
  IN_PROGRESS = "in_progress",
  COMPLETE = "complete",
  FAILED = "failed",
}

enum RequestType {
  START_ACTIVITY_PARSING = "start_activity_parsing",
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
  message: string;
}

// Interfaces specific to each API.

interface StartActivityParsingRequst extends BaseRequest {
  linkedin_url: string;
}

interface StartActivityParsingResponse extends BaseResponse {
  status: LinkedInActivityParsingStatus;
}

const activityParserExtensionId = import.meta.env
  .VITE_ACTIVITY_PARSER_EXTENSION_ID;

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
    throw new Error((response as ErrorResponse).message);
  }

  return response as StartActivityParsingResponse;
};

// Returns current linkedin activity parsing status.
export const getLinkedInActivityParsingStatus =
  (): LinkedInActivityParsingStatus => {
    validateExtensionExists();
    // TODO: Fetch status from extension.
    return LinkedInActivityParsingStatus.IN_PROGRESS;
  };

const validateExtensionExists = () => {
  if (!chrome || !chrome.runtime) {
    throw new Error(
      "Chrome extension is not installed, please install it from the Chrome Web Store!"
    );
  }
};
