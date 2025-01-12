import 'webextension-polyfill';

// Common Interfaces for all requests

enum RequestType {
  START_ACTIVITY_PARSING = 'start_activity_parsing',
}

interface BaseRequest {
  request_type: RequestType;
}

enum ResponseType {
  SUCCESS = 'success',
  ERROR = 'error',
}

interface BaseResponse {
  type: ResponseType;
}

interface ErrorResponse extends BaseResponse {
  message: string;
}

// Details of each request and response.

interface StartActivityParsingRequst extends BaseRequest {
  linkedin_url: string;
}

// Listens to messages from Userport's web app.
chrome.runtime.onMessageExternal.addListener(
  (message: BaseRequest, _, sendResponse: (response: BaseResponse) => void) => {
    try {
      const requestType = message.request_type;
      if (requestType == RequestType.START_ACTIVITY_PARSING) {
        const req = message as StartActivityParsingRequst;
        const linkedin_url = req.linkedin_url;
        if (!linkedin_url) {
          throw new Error('LinkedIn URL not present in Start Activity Payload');
        }

        // TODO: Open new tab to activity page of the given LinkedIn URL.
        const activityEndpoint = 'recent-activity/all/';
        const activityURL = linkedin_url.endsWith('/')
          ? linkedin_url + activityEndpoint
          : `${linkedin_url}/${activityEndpoint}`;
        chrome.tabs.create({ url: activityURL, active: false }).then(tab => {
          sendResponse({ type: ResponseType.SUCCESS });
        });

        // Since tab creation is asynchronous, must send an explicit `true`.
        return true;
      }
    } catch (error) {
      const resp: ErrorResponse = { type: ResponseType.ERROR, message: String(error) };
      sendResponse(resp);
    }
  },
);
