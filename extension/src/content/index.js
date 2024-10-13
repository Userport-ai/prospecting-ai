import { runtime } from "webextension-polyfill";

// Listen to messages related to this tab sent by the Service worker. Returns true if it is a valid LinkedIn profile URL and false otherwise.
runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "linkedin-profile-detected") {
    // It's possible the page has intermediate URL like https://www.linkedin.com/in/ACoAADagalYBPENv8mrVmPUm81VjZLC-w65uuZE/
    // which then becomes https://www.linkedin.com/in/hitesh-z-a9ab17216/. We want to make sure to not send back the former
    // to the background script to check research status. So we want to check if the DOM has the expected tag to differentiate
    // the two URLs.
    const element = document.querySelector("a.ember-view");
    if (element === null) {
      // URL is not final. Ex: https://www.linkedin.com/in/ACoAADagalYBPENv8mrVmPUm81VjZLC-w65uuZE/.
      // Do nothing and wait for service worker to return the final URL.
      sendResponse(false);
    } else {
      sendResponse(true);
    }

    // Return false since sendResponse is called synchronously.
    // Reference: https://developer.chrome.com/docs/extensions/develop/concepts/messaging.
    return false;
  }
});
