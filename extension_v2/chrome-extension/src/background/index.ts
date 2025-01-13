import 'webextension-polyfill';
import { startActivityParsing } from './activity';
import { getActivityData } from './activityDataStorage';
import { ActivityParsingStatus } from './common';

// Common Interfaces for all requests

enum RequestType {
  START_ACTIVITY_PARSING = 'start_activity_parsing',
  GET_ACTIVITY_PARSING_RESULT = 'get_activity_parsing_result',
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
  error_message: string;
}

// Details of each request and response.

interface StartActivityParsingRequest extends BaseRequest {
  linkedin_url: string;
}

interface StartActivityParsingResponse extends BaseResponse {
  tab_id: number; // ID of the tab where activity parsing is taking place.
  status: ActivityParsingStatus;
}

interface GetActivityParsingResultRequest extends BaseRequest {
  tab_id: number;
  linkedin_url: string;
}

interface GetActivityParsingResultResponse extends BaseResponse {
  status: ActivityParsingStatus;
  parsed_data: {
    posts_html?: string | null;
    comments_html?: string | null;
    reactions_html?: string | null;
  };
}

// Listens to messages from Userport's web app.
chrome.runtime.onMessageExternal.addListener(
  (message: BaseRequest, _, sendResponse: (response: BaseResponse) => void) => {
    try {
      switch (message.request_type) {
        case RequestType.START_ACTIVITY_PARSING:
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
                tab_id: tab.id,
                status: ActivityParsingStatus.IN_PROGRESS,
              } as StartActivityParsingResponse);
            })
            .catch(error => sendResponse({ type: ResponseType.ERROR, error_message: String(error) } as ErrorResponse));

          // Since tab creation is asynchronous, must send an explicit `true`.
          return true;

        case RequestType.GET_ACTIVITY_PARSING_RESULT:
          // Read storage and return the result.
          const getReq = message as GetActivityParsingResultRequest;
          const tabId = getReq.tab_id;
          const linkedinUrl = getReq.linkedin_url;
          getActivityData(tabId)
            .then(data => {
              if (data === null) {
                // Activity data not found in storage.
                throw new Error(`Activity Parsing failed to commence for URL: ${linkedinUrl}`);
              }
              if (data.status === ActivityParsingStatus.FAILED) {
                throw new Error(`Activity Parsing failed with error: ${data.error} for URL: ${linkedinUrl}`);
              }
              if (data.status === ActivityParsingStatus.IN_PROGRESS) {
                sendResponse({
                  type: ResponseType.SUCCESS,
                  status: ActivityParsingStatus.IN_PROGRESS,
                } as GetActivityParsingResultResponse);
                return;
              }
              // Parsing is complete.
              if (!data.parsed_data) {
                // Parsing data is not populated.
                throw new Error(`Activity Parsing completed but data missing for URL: ${linkedinUrl}`);
              }
              // Parsing is successful, send response and close the tab.
              sendResponse({
                type: ResponseType.SUCCESS,
                status: ActivityParsingStatus.COMPLETE,
                parsed_data: data.parsed_data,
              } as GetActivityParsingResultResponse);
              // Close tab.
              chrome.tabs.remove(tabId);
            })
            .catch(error => {
              sendResponse({ type: ResponseType.ERROR, error_message: String(error) } as ErrorResponse);
              // Close tab.
              chrome.tabs.remove(tabId);
            });

          // Since fetching activity data is asynchronous, must send an explicit `true`.
          return true;
        default:
          // Nothing to do.
          return false;
      }
    } catch (error) {
      sendResponse({ type: ResponseType.ERROR, error_message: String(error) } as ErrorResponse);
      return false;
    }
  },
);
