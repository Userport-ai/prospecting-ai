import { runtime } from "webextension-polyfill";

const linkedInDomain = "https://www.linkedin.com";

// Helper to fetch all activity buttons that returns a Nodelist.
// Caution: Use forEach to loop over the Nodelist not regular for loop.
function getActivityButtons() {
  return document.querySelectorAll(
    "div.pv-recent-activity-detail__core-rail div.mb3 button"
  );
}

// Helper to fetch node element containing all the activity content.
function getActivityOnPage() {
  // First <ul> tag with given CSS selector contains list of activities.
  return document.querySelector(
    "div.pv-recent-activity-detail__core-rail div.pv0 ul"
  );
}

// Returns current button name on activity page and null otherwise.
function getCurrentBtnName() {
  var curBtnName = null;
  getActivityButtons().forEach((elem, idx) => {
    // Check for currently selected activity's button to exist on page.
    if (elem.classList.contains("artdeco-pill--selected")) {
      const spanElem = elem.querySelector("span");
      if (spanElem !== null) {
        curBtnName = spanElem.textContent.trim();
        // No way to break out of forEach.
      }
    }
  });
  return curBtnName;
}

// Helper to fetch node list containing all the activity contents as HTML <li> elements.
function getActivityListOnPage() {
  const activityParentElem = getActivityOnPage();
  // Fetch direct children of an element: https://stackoverflow.com/questions/3680876/using-queryselectorall-to-retrieve-direct-children.
  return activityParentElem.querySelectorAll(":scope > li");
}

// Listen to messages related to this tab sent by the Service worker. Returns true if it is a valid LinkedIn profile URL and false otherwise.
runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "linkedin-profile-detected") {
    // We expect the user to be be on the recent-activity URL on LinkedIn.
    // If so, we return the their name and linkedin profile URL and if not, we return null.
    const element = document.querySelector(
      "div#recent-activity-top-card div.break-words a"
    );
    if (element === null) {
      // This is not a valid URL, return null.
      sendResponse(null);
      return false;
    }

    const name = element.querySelector("h3").textContent.trim();
    // This will give a relative path with format "/in/<username>".
    const relativeProfileURL = element.getAttribute("href").trim();
    const absoluteProfileURL = linkedInDomain.concat(relativeProfileURL);
    sendResponse({ name: name, profileURL: absoluteProfileURL });

    // Return false since sendResponse is called synchronously.
    // Reference: https://developer.chrome.com/docs/extensions/develop/concepts/messaging.
    return false;
  }
  if (request.action === "get-activity-buttons") {
    // Get the activity button elements that are wanted.
    const wantedActivities = request.wantedActivities;
    var btnIndexMap = {};
    getActivityButtons().forEach((elem, idx) => {
      const btnName = elem.querySelector("span").textContent.trim();
      if (wantedActivities.includes(btnName)) {
        btnIndexMap[btnName] = idx;
      }
    });
    sendResponse(btnIndexMap);
    return false;
  }

  if (request.action === "get-current-activity-html") {
    let curBtnName = getCurrentBtnName();
    if (curBtnName === null) {
      console.error("Did not find button name Activity on page!");
      sendResponse(null);
      return false;
    }

    // Get data.
    var htmlNode = getActivityOnPage();
    if (htmlNode === null) {
      console.error(`HTML for activity: ${curBtnName} not found on page`);
      sendResponse(null);
      return false;
    }

    sendResponse({ html: htmlNode.outerHTML, name: curBtnName });
    return false;
  }

  if (request.action === "scroll-down-to-page") {
    const activityNodeList = getActivityListOnPage();
    if (activityNodeList.length === 0) {
      // No activity list found.
      console.log("No activities found on current activity page to scroll");
      sendResponse(false);
      return false;
    }

    // Scroll to last node in current page.
    // TODO: make the scrolling smoother by using a timer. Ex: https://stackoverflow.com/questions/15935318/smooth-scroll-to-top
    // or https://www.linkedin.com/pulse/scroll-bottom-javascript-frontend-interview-questions-swtuf/.
    const lastElem = activityNodeList[activityNodeList.length - 1];
    lastElem.scrollIntoView({ behavior: "smooth" });

    sendResponse(true);
    return false;
  }

  if (request.action === "click-activity-button") {
    // Click activity button with given index. Index was fetched previously
    // with a different command in the same content script.
    var success = false;
    getActivityButtons().forEach((btnElem, idx) => {
      if (idx === request.btnIndex) {
        btnElem.click();
        success = true;
        // No way to break out of forEach loop.
      }
    });
    sendResponse(success);
    return false;
  }
});
