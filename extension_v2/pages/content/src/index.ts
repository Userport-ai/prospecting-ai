// Request from Service worker.
enum RequestType {
  FETCH_ACTIVITY = 'fetch_activity',
}

// Names of the desired activity buttons.
enum ActivityButton {
  POSTS = 'Posts',
  COMMENTS = 'Comments',
  REACTIONS = 'Reactions',
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

// Connection name of the port used.
const portConnectionName = 'activity_scraper';

// Helper to fetch all activity buttons that returns a Nodelist.
// Caution: Use forEach to loop over the Nodelist not regular for loop.
const getActivityButtons = () => {
  return document.querySelectorAll('div.pv-recent-activity-detail__core-rail div.mb3 button');
};

// Get Button element with given name or null if it doesn't exist.
const getButtonElem = (btnName: ActivityButton): HTMLElement | null => {
  var btnElem = null;
  getActivityButtons().forEach((elem, _) => {
    const span = elem.querySelector('span');
    if (span && span.textContent && span.textContent.trim() === btnName) {
      btnElem = elem;
      // No way to break out of forEach.
    }
  });
  return btnElem;
};

// Fetch HTML Element containing all the activity content in the given page.
const getPageActivityElem = (): Element | null => {
  // First <ul> tag with given CSS selector contains list of activities.
  return document.querySelector('div.pv-recent-activity-detail__core-rail div.pv0 ul');
};

// Helper that returns a promise that resolves after given number of milliseconds to simulate delay.
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

// Main method to listen to messages from Service Worker.

// Reference: https://developer.chrome.com/docs/extensions/develop/concepts/messaging#connect.
chrome.runtime.onConnect.addListener(port => {
  if (port.name !== portConnectionName) {
    // Invalid port.
    port.disconnect();
    return;
  }

  // Handler for listening to messages.
  port.onMessage.addListener((msg: BaseActivityRequest) => {
    switch (msg.type) {
      case RequestType.FETCH_ACTIVITY:
        const btnName = (msg as FetchActivityRequest).name;
        const btnElem = getButtonElem(btnName);
        if (btnElem === null) {
          // If Button doesn't exist, then return null HTML.
          // Either lead does not have this activity or made it
          // is like "Reactions" which can be hidden under a dropdown.
          port.postMessage({ name: btnName, html: null } as FetchActivityResponse);
          return;
        }

        // Click on the button and wait for activity to reload with new data.
        btnElem.click();
        delay(6000).then(() => {
          // Fetch activity HTML.
          const activityElem = getPageActivityElem();
          const html = activityElem ? activityElem.outerHTML : null;
          port.postMessage({ name: btnName, html: html });
        });

        break;
      default:
        // Do nothing.
        break;
    }
  });
});
