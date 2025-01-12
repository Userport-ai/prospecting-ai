import 'webextension-polyfill';
import { startActivityParsing } from './activity';

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

enum ActivityParsingStatus {
  IN_PROGRESS = 'in_progress',
  COMPLETE = 'complete',
  FAILED = 'failed',
}

// Details of each request and response.

interface StartActivityParsingRequest extends BaseRequest {
  linkedin_url: string;
}

interface StartActivityParsingResponse extends BaseResponse {
  status: ActivityParsingStatus;
}

// Listens to messages from Userport's web app.
chrome.runtime.onMessageExternal.addListener(
  (message: BaseRequest, _, sendResponse: (response: BaseResponse) => void) => {
    try {
      const requestType = message.request_type;
      if (requestType == RequestType.START_ACTIVITY_PARSING) {
        const req = message as StartActivityParsingRequest;
        const linkedin_url = req.linkedin_url;
        if (!linkedin_url) {
          throw new Error('LinkedIn URL not present in Start Activity Payload');
        }

        // Open new tab to activity page of the given LinkedIn URL.
        const activityEndpoint = 'recent-activity/all/';
        const activityURL = linkedin_url.endsWith('/')
          ? linkedin_url + activityEndpoint
          : `${linkedin_url}/${activityEndpoint}`;
        chrome.tabs
          .create({ url: activityURL, active: false })
          .then(tab => {
            if (!tab.id) {
              throw new Error(`Tab Id does not exist in opened tab for URL: ${activityURL}`);
            }
            startActivityParsing(tab.id, activityURL);

            // Send response to client.
            sendResponse({
              type: ResponseType.SUCCESS,
              status: ActivityParsingStatus.IN_PROGRESS,
            } as StartActivityParsingResponse);
          })
          .catch(error => sendResponse({ type: ResponseType.ERROR, message: String(error) } as ErrorResponse));

        // Since tab creation is asynchronous, must send an explicit `true`.
        return true;
      }
    } catch (error) {
      sendResponse({ type: ResponseType.ERROR, message: String(error) } as ErrorResponse);
    }
  },
);
