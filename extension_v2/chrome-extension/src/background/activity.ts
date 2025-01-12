import { getActivityData, setActivityData } from './activityDataStorage';
import { ParsingStatus } from './common';

// Connection name of the port used.
const portConnectionName = 'activity_scraper';

// Names of the desired activity buttons.
enum ActivityButton {
  POSTS = 'Posts',
  COMMENTS = 'Comments',
  REACTIONS = 'Reactions',
}

const wantedActivities = [ActivityButton.POSTS, ActivityButton.COMMENTS, ActivityButton.REACTIONS];

// Common requests.
enum RequestType {
  FETCH_ACTIVITY = 'fetch_activity',
}

interface BaseActivityRequest {
  type: RequestType;
}

// Fetch Activity for given button.
interface FetchActivityRequest extends BaseActivityRequest {
  name: ActivityButton;
}

// Fetch Activity Response provides the parsed HTML for given Activity.
interface FetchActivityResponse {
  name: ActivityButton;
  html: string | null;
}

// Manages activity parsing communication with content Script.
export const startActivityParsing = async (tabId: number, tabUrl: string) => {
  // TODO: Store activity state for given Tab Id.
  await setActivityData(tabId, { status: ParsingStatus.NOT_STARTED, last_status: null, url: tabUrl });

  // Wait for some time to ensure that the Activity page loads and Content script is ready
  // to accept connections from the service worker.
  delay(4000);
  // Create a long lived connection between Extension and Content Script.;
  var port = chrome.tabs.connect(tabId, { name: portConnectionName });

  // Handle disconnections from Content Script.
  port.onDisconnect.addListener(port => {
    getActivityData(tabId).then(data =>
      setActivityData(tabId, {
        status: ParsingStatus.FAILED,
        url: tabUrl,
        last_status: data ? data.status : null,
        error: `Failed to connect to Activity URL: ${tabUrl} with error: ${chrome.runtime.lastError}`,
      }),
    );
  });

  // Send message to content script to start parsing activity.
  // TODO: Randomize the first activity fetched.

  const curActivityButton = wantedActivities[0];
  port.postMessage({ type: RequestType.FETCH_ACTIVITY, name: curActivityButton } as FetchActivityRequest);

  // Handle messages received from content script.
  port.onMessage.addListener((message: FetchActivityResponse) => {
    console.log('Fetcha activity response: ', message);
  });
};

// Returns a promise that resolves after given number of milliseconds.
// Use to retry DOM fetches that take some time to load.
// Reference: https://stackoverflow.com/questions/70401067/how-do-you-call-a-function-every-second-in-a-chrome-extension-manifest-v3-backgr.
async function delay(msToDelay: number) {
  return new Promise<void>((success, failure) => {
    const completionTime = new Date().getTime() + msToDelay;
    while (true) {
      if (new Date().getTime() >= completionTime) {
        success();
        break;
      }
    }
  });
}
