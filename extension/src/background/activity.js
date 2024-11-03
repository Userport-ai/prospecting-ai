import { tabs } from "webextension-polyfill";
import { getTabData, setTabData } from "./tab-state";
import { captureEvent } from "./metrics";

// Module constants.
const PostsActivity = "Posts";
const CommentsActivity = "Comments";
const ReactionsActivity = "Reactions";
const wantedActivities = [PostsActivity, CommentsActivity, ReactionsActivity];

// Start activity research on given tab.
// We will need to store the activity research state in storage because: [1] Popup UI should
// reflect updated local state when it is closed and opened while is activity research is ongoing.
// and [2] Tab updated listener should redirect logic to this module is the current state is activity
// research.
export async function startActivityResearch(tabId) {
  console.log("Activity research has started");
  // Start with storing empty activity data.
  await setActivityData(tabId, { btnIndexMap: {}, visitedMap: {} });

  // Fetch button text to index map from content script.
  // This map contains Button name (Ex: Posts, Comments) to their index (Ex: 0, 1 etc.)
  // as key value pairs.
  const btnIndexMap = await tabs.sendMessage(tabId, {
    action: "get-activity-buttons",
    wantedActivities: wantedActivities,
  });

  // Store button index map.
  var activityData = { btnIndexMap: btnIndexMap, visitedMap: {} };
  await setActivityData(tabId, activityData);
}

// Fetch HTML from current activity tab in given page.
// This method is called once for each activity (Posts, Comments etc.)
// and once all activity buttons are traversed, it returns True to signal
// research completion. If there are more buttons to traverse, it returns False.
export async function fetchCurrentActivityHTML(tabId) {
  // Wait for HTML activity to load in current page. Usually takes a few seconds
  // if page is being loaded, so we need to retry a few times.
  var count = 0;
  var result = null;
  while (count < 4) {
    result = await tabs.sendMessage(tabId, {
      action: "get-current-activity-html",
    });
    if (result !== null) {
      break;
    }
    // Wait and try again after 2 seconds.
    await delay(2000);
    count += 1;
  }
  if (result === null) {
    // Failed to fetch activity data in current page due to some error, return False.
    console.error("Could not fetch HTML for activity in tab: ", tabId);
    return false;
  }
  // Get current activity button name and HTML of the activity from the result.
  var btnName = result.name;
  var btnHTML = result.html;

  if (btnName === ReactionsActivity) {
    // Scroll down to page to collect more reactions.
    // We need to do this multiple times because, not all reactions are loaded in the given page so the
    // the scroll down to page goes only till end of currently loaded reactions as opposed to actually last <li>
    // element.
    // For example: last <li> index = 20 but the actual page scroll will be to <li> element index 8 since other elements have
    // not loaded yet. To solve for this, we scroll multiple times to load desired number of reactions.
    for (let i = 0; i < 2; i++) {
      // Random delay between 2-4 seconds before starting scroll.
      const scrollDelay = Math.floor(Math.random() * 2000 + 2000);
      await delay(scrollDelay);

      const res = await tabs.sendMessage(tabId, {
        action: "scroll-down-to-page",
      });
      if (!res) {
        // Some failure in scrolling down in page.
        console.error("Could not scroll down to page in tab: ", tabId);
        return false;
      }
    }

    // Random delay between 1-3 seconds for final scroll to load before reading activity HTML.
    const scrollDelay = Math.floor(Math.random() * 3000 + 1000);
    await delay(scrollDelay);

    // Fetch Reactions HTML now that page has been scrolled and we have more reactions.
    result = await tabs.sendMessage(tabId, {
      action: "get-current-activity-html",
    });
    if (result === null) {
      // Failed to fetch activity data in current page due to some error, return False.
      console.error(
        "Could not fetch HTML for Scrolled activity in tab: ",
        tabId
      );
      return false;
    }
    btnName = result.name;
    btnHTML = result.html;
  }

  // Stor btnName and btnHTML to visited map and update storage.
  var activityData = await getActivityData(tabId);
  if (activityData === null) {
    console.error(
      "Failed to find activity data in storage for tab ID: ",
      tabId
    );
    return false;
  }
  activityData.visitedMap[btnName] = btnHTML;
  await setActivityData(tabId, activityData);

  // Find next button to visit.
  const nextBtnIdx = await nextButtonToVisit(activityData);
  if (nextBtnIdx === null) {
    // Done fetching data from all the buttons.
    console.log("Activity Research is complete");

    // Send event.
    captureEvent("extension_activity_research_complete");
    return true;
  }

  // Add Random delay of 1-3 seconds before clicking next button.
  const delayms = Math.floor(Math.random() * 3000 + 1000);
  await delay(delayms);

  // Send message to content script to click the next button.
  const success = await tabs.sendMessage(tabId, {
    action: "click-activity-button",
    btnIndex: nextBtnIdx,
  });
  if (!success) {
    console.error("Failed to click next button for index: ", nextBtnIdx);
    // TODO: do something like sending an alert to posthog.
  }
  return false;
}

// Returns next button to visit's index from activity data in storage.
// Returns null if no more buttons to visit (since all have been visited).
async function nextButtonToVisit(activityData) {
  const btnIndexMap = activityData.btnIndexMap;
  const visitedMap = activityData.visitedMap;
  var nextBtnIdx = null;
  for (const btnName in btnIndexMap) {
    if (btnName in visitedMap) {
      // Already visited, do nothing.
      continue;
    }
    nextBtnIdx = btnIndexMap[btnName];
    break;
  }
  return nextBtnIdx;
}

// Returns activity data from storage. If not present, returns null.
export async function getActivityData(tabId) {
  const data = await getTabData(tabId);
  if (data && "activityData" in data) {
    return data.activityData;
  }
  return null;
}

// Helper to update storage with given activity state.
async function setActivityData(tabId, activityData) {
  var data = await getTabData(tabId);
  data.activityData = activityData;
  setTabData(tabId, data);
}

// Helper to get Posts activity data from given activityData.
// Returns null if not found.
export function getPostsActivityData(activityData) {
  if ("visitedMap" in activityData) {
    if (PostsActivity in activityData.visitedMap) {
      return activityData.visitedMap[PostsActivity];
    }
  }
  console.error("Could not find Posts activity in data: ", activityData);
  return null;
}

// Helper to get Comments activity data from given activityData.
// Returns null if not found.
export function getCommentsActivityData(activityData) {
  if ("visitedMap" in activityData) {
    if (CommentsActivity in activityData.visitedMap) {
      return activityData.visitedMap[CommentsActivity];
    }
  }
  console.error("Could not find Comments activity in data: ", activityData);
  return null;
}

// Helper to get Reactions activity data from given activityData.
// Returns null if not found.
export function getReactionsActivityData(activityData) {
  if ("visitedMap" in activityData) {
    if (ReactionsActivity in activityData.visitedMap) {
      return activityData.visitedMap[ReactionsActivity];
    }
  }
  console.error("Could not find Reactions activity in data: ", activityData);
  return null;
}

// Returns a promise that resolves after given number of milliseconds.
// Use to retry DOM fetches that take some time to load.
// Reference: https://stackoverflow.com/questions/70401067/how-do-you-call-a-function-every-second-in-a-chrome-extension-manifest-v3-backgr.
async function delay(msToDelay) {
  return new Promise((success, failure) => {
    const completionTime = new Date().getTime() + msToDelay;
    while (true) {
      if (new Date().getTime() >= completionTime) {
        success();
        break;
      }
    }
  });
}
