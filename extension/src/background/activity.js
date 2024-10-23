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
  // Fetch HTML activity data from current page.
  var count = 0;
  var result = null;
  while (count < 3) {
    result = await tabs.sendMessage(tabId, {
      action: "get-current-activity-html",
      wantedActivities: wantedActivities,
    });
    if (result !== null) {
      break;
    }
    // Wait and try again after 2 seconds.
    await delay(2000);
    count += 1;
  }
  if (result === null) {
    console.error("Could not fetch HTML for activity in tab: ", tabId);
    return false;
  }
  const btnName = result.name;
  const btnHTML = result.html;

  // Add data to visited map and update storage.
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

  // Add Random delay.
  const delayms = Math.floor(Math.random() * 3000 + 1000);
  await delay(delayms);

  // Send message to content script to click the next button.
  const success = await tabs.sendMessage(tabId, {
    action: "click-activity-button",
    btnIndex: nextBtnIdx,
  });
  if (!success) {
    console.error("Failed to click next button for index: ", nextBtnIdx);
    // TODO: do something.
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
