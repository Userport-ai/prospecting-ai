import { runtime } from "webextension-polyfill";

// overlayhref is of the format: in/gobikrishnan-t-b0894716b/overlay/about-this-profile.
// This method will extract LinkedIn username and return the URL. Ex: https://www.linkedin.com/in/gobikrishnan-t-b0894716b
function getLinkedInProfileURL(overlayhref) {
  const overLayArr = overlayhref.split("/");
  const inIdx = overLayArr.findIndex((str) => str === "in");
  if (inIdx === -1 || inIdx === overLayArr.length - 1) {
    console.error(
      `Could not extract LinkedIn Username from overlay Href:${overlayhref} with invalid inIdx value: ${inIdx}`
    );
    return null;
  }
  // Username is the next element in the array.
  const userName = overLayArr[inIdx + 1];
  return `https://www.linkedin.com/in/${userName}`;
}

// Setup observer for DOM changes for the given element in the page so that we can detect when a new LinkedIn Profile is opened.
function setUpMutationObserver(element) {
  // Options for the observer (which changes to observe)
  const config = { attributes: true, childList: true, subtree: true };

  // Create observer.
  const observer = new MutationObserver(handleDomChanged);

  // Start observing the element.
  observer.observe(element, config);
}

// Handler for when DOM changes occur. We don't care about the specifics, just know that
// this is a signal for LinkedIn profile to be recomputed.
function handleDomChanged(mutationList, observer) {
  console.log("Dom has changed");
}

function init() {
  // Initial page URL on page load. May not be the final URL of the profile, so we need to start
  // a timer, wait and then fetch the actual page.
  // It's possible page was still loading, so will wait and try again.
  var timer = setInterval(() => {
    const element = document.querySelectorAll("a.ember-view")[0];
    if (element !== undefined) {
      const href = element.getAttribute("href");
      const linkedInProfileUrl = getLinkedInProfileURL(href);
      if (linkedInProfileUrl) {
        // Send message to background worker.
        runtime.sendMessage({
          action: "linkedin-url-detected",
          linkedInProfileUrl: linkedInProfileUrl,
        });

        // Since LinkedIn UI is an SPA, we can't rely on only on page reloads to get profile URL.
        // Set up Mutation Observer to observe changes.
        setUpMutationObserver(element);
      }

      // Clear timer.
      clearInterval(timer);
    }
  }, 1000);
}

init();
