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
  return document.querySelector(
    "div.pv-recent-activity-detail__core-rail div.pv0 ul"
  );
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
    // Find currently selected activity button's name.
    var curBtnName = null;
    getActivityButtons().forEach((elem, idx) => {
      if (elem.classList.contains("artdeco-pill--selected")) {
        const spanElem = elem.querySelector("span");
        if (spanElem !== null) {
          curBtnName = spanElem.textContent.trim();
          // No way to break out of forEach.
        }
      }
    });
    if (curBtnName === null) {
      console.error("Did not find selected activity on page!");
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

  if (request.action === "click-activity-button") {
    // Click activity button with given index. Index was fetched previously
    // with a different command in the same content script.
    var success = false;
    getActivityButtons().forEach((btnElem, idx) => {
      if (idx === request.btnIndex) {
        btnElem.click();
        success = true;
      }
    });
    sendResponse(success);
    return false;
  }
});
