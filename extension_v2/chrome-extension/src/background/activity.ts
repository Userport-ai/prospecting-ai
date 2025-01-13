import { getActivityData, setActivityData } from './activityDataStorage';
import { ActivityParsingStatus } from './common';

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
  CLICK_ACTIVITY_BUTTON = 'click_activity_button',
  FETCH_ACTIVITY = 'fetch_activity',
}

// We use the same interface for request and response in many cases
// to keep things simple. When one of them is different, we extend this
// interface.
interface BaseActivityRequest {
  type: RequestType;
  name: ActivityButton;
}

// Fetch Activity Response provides the parsed HTML for given Activity.
interface FetchActivityResponse extends BaseActivityRequest {
  html: string | null;
}

// Manages activity parsing communication with content Script.
export const startActivityParsing = async (tabId: number, tabUrl: string) => {
  // TODO: Store activity state for given Tab Id.
  await setActivityData(tabId, {
    status: ActivityParsingStatus.IN_PROGRESS,
    last_status: null,
    url: tabUrl,
  });

  // Wait for some time to ensure that the Activity page loads and Content script is ready
  // to accept connections from the service worker.
  delay(4000);
  // Create a long lived connection between Extension and Content Script.;
  var port = chrome.tabs.connect(tabId, { name: portConnectionName });

  // Handle disconnections from Content Script.
  port.onDisconnect.addListener(port => {
    getActivityData(tabId).then(data =>
      // TODO: Do not set as failed if status is completed already.
      setActivityData(tabId, {
        status: ActivityParsingStatus.FAILED,
        url: tabUrl,
        last_status: data ? data.status : null,
        error: `Failed to connect to Activity URL: ${tabUrl} with error: ${chrome.runtime.lastError}`,
      }),
    );
  });

  // Send message to content script to start parsing activity.
  const randomIndex = Math.floor(Math.random() * wantedActivities.length);
  const nextActivity = wantedActivities[randomIndex];
  port.postMessage({
    type: RequestType.CLICK_ACTIVITY_BUTTON,
    name: nextActivity,
  } as BaseActivityRequest);

  // Handle messages received from content script.
  port.onMessage.addListener((message: BaseActivityRequest) => {
    switch (message.type) {
      case RequestType.CLICK_ACTIVITY_BUTTON:
        // Button clicked, we should wait for 6-8 seconds to the page load and then fetch HTML.
        const waitDelay = Math.floor(Math.random() * 6000 + 2000);
        delay(waitDelay);

        port.postMessage({ type: RequestType.FETCH_ACTIVITY, name: message.name } as BaseActivityRequest);
        break;
      case RequestType.FETCH_ACTIVITY:
        const html = (message as FetchActivityResponse).html;
        // HTML has been fetched, update it in storage.
        getActivityData(tabId).then(data => {
          if (!data) {
            // Error state that there is no storage data.
            setActivityData(tabId, {
              status: ActivityParsingStatus.FAILED,
              url: tabUrl,
              last_status: null,
              error: `Parsing state was not stored for: ${tabUrl}`,
            });
            return;
          }

          // Update parsed data.
          var parsed_data = data.parsed_data ? data.parsed_data : {};
          if (message.name === ActivityButton.POSTS) {
            parsed_data.posts_html = html;
          } else if (message.name === ActivityButton.COMMENTS) {
            parsed_data.comments_html = html;
          } else if (message.name === ActivityButton.REACTIONS) {
            parsed_data.reactions_html = html;
          }
          data.parsed_data = parsed_data;

          // Find next activity to scrape.
          var remainingActivities: ActivityButton[] = [];
          if (parsed_data.posts_html === undefined) {
            remainingActivities.push(ActivityButton.POSTS);
          }
          if (parsed_data.comments_html === undefined) {
            remainingActivities.push(ActivityButton.COMMENTS);
          }
          if (parsed_data.reactions_html === undefined) {
            remainingActivities.push(ActivityButton.REACTIONS);
          }

          if (remainingActivities.length === 0) {
            // If no more activities to fetch, update status to COMPLETE and return.
            data.last_status = data.status;
            data.status = ActivityParsingStatus.COMPLETE;
            setActivityData(tabId, data);
            return;
          }
          // Update activity data and fetch next activity.
          setActivityData(tabId, data).then(() => {
            // Pick a random Index.
            const randomIndex = Math.floor(Math.random() * remainingActivities.length);
            const nextActivity = remainingActivities[randomIndex];
            port.postMessage({ type: RequestType.CLICK_ACTIVITY_BUTTON, name: nextActivity } as BaseActivityRequest);
          });
        });
        break;
      default:
        // Do nothing;
        break;
    }
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
