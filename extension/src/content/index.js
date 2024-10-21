import { runtime } from "webextension-polyfill";

const linkedInDomain = "https://www.linkedin.com";

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
});
