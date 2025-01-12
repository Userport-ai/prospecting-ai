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

interface StartActivityParsingRequst extends BaseRequest {
  linkedin_url: string;
}

const activityParserExtensionId = import.meta.env
  .VITE_ACTIVITY_PARSER_EXTENSION_ID;

// Reference: https://developer.chrome.com/docs/extensions/develop/concepts/messaging#external.
export const startLinkedInActivityParsing = async (linkedin_url: string) => {
  if (!chrome || !chrome.runtime) {
    throw new Error("Chrome extension is not installed");
  }
  const request: StartActivityParsingRequst = {
    request_type: RequestType.START_ACTIVITY_PARSING,
    linkedin_url: linkedin_url,
  };

  const response: BaseResponse = await chrome.runtime.sendMessage(
    activityParserExtensionId,
    request
  );

  if (response.type === ResponseType.ERROR) {
    throw new Error((response as ErrorResponse).message);
  }

  console.log("got response: ", response);
};
