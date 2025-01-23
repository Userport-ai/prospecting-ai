// Request from Service worker.
enum RequestType {
  CLICK_ACTIVITY_BUTTON = 'click_activity_button',
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
  name: ActivityButton;
}

// Fetch Activity Response provides the parsed HTML for given Activity.
interface FetchActivityResponse extends BaseActivityRequest {
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
    const btnName = msg.name;
    switch (msg.type) {
      case RequestType.CLICK_ACTIVITY_BUTTON:
        // Click activity button to load activity content.
        const btnElem = getButtonElem(btnName);
        if (btnElem === null) {
          // If Button doesn't exist, return null HTML directly.
          // Lead does not have this activity.
          port.postMessage({ type: msg.type, name: btnName, html: null } as FetchActivityResponse);
          return;
        }

        // Click on the button.
        btnElem.click();
        port.postMessage({ type: RequestType.CLICK_ACTIVITY_BUTTON, name: btnName });
        break;
      case RequestType.FETCH_ACTIVITY:
        // Fetch activity HTML now that button has been clicked.
        // We also assume that the service worker has waited enough
        // for the activity page to have been loaded.
        const activityElem = getPageActivityElem();
        const html = activityElem ? activityElem.outerHTML : null;
        port.postMessage({ type: msg.type, name: btnName, html: html } as FetchActivityResponse);
        break;
      default:
        // Do nothing.
        break;
    }
  });
});
