import { runtime, tabs, alarms } from "webextension-polyfill";
import {
  handleLoginTabClosed,
  isUserLoggingIn,
  logOut,
  startLogin,
} from "./login";
import { getUserObj } from "./auth";
import { captureEvent } from "./metrics";
import {
  clearAlarm,
  clearTabData,
  createAlarm,
  createNotification,
  doesAlarmExist,
  getTabData,
  setTabData,
  tabIdKeyToNumber,
} from "./tab-state";
import {
  getActivityData,
  startActivityResearch,
  fetchCurrentActivityHTML,
  getPostsActivityData,
  getCommentsActivityData,
  getReactionsActivityData,
} from "./activity";

// Module constants.
const leadReportStatusSuccess = "complete";
const leadReportStatusFailed = "failed_with_errors";
const callOrigin = "extension";

// Helper that creates lead profile from given tab Id, Lead LinkedIn URL and report (can be null) and stores it in storage.
// It also starts an alarm if the lead status exists but is not in failed or complete status.
function createLeadProfile(
  tabId,
  profileName,
  linkedInProfileUrl,
  lead_research_report
) {
  const leadProfile = {
    name: profileName,
    url: linkedInProfileUrl,
    lead_research_report: lead_research_report,
  };

  // Add lead profile to storage.
  // This will delete any existing activity data which is expected
  // since activity data is only for the purposes of researching activity
  // and should have complete by the time this method is invoked.
  setTabData(tabId, leadProfile);

  // If report status is not complete or failed, then create an alarm to poll status periodically.
  const report_status = lead_research_report
    ? lead_research_report.status
    : null;
  var periodicCheck = false;
  if (
    report_status &&
    report_status !== leadReportStatusSuccess &&
    report_status !== leadReportStatusFailed
  ) {
    // Report does not exist or is in progress.
    // We should check report status periodically.
    periodicCheck = true;
  }

  // Check if alarm already exists.
  doesAlarmExist(tabId).then((exists) => {
    if (!exists) {
      // Alarm does not exist.
      if (periodicCheck) {
        console.log("creating alarm for tab: ", tabId);
        createAlarm(tabId);
      }
      return;
    }

    // Alarm already exists.
    if (!periodicCheck) {
      if (
        report_status === leadReportStatusSuccess ||
        report_status === leadReportStatusFailed
      ) {
        // Create a notification that lead research is now complete.
        var notifTitle = `Research Complete for ${profileName}`;
        var notifMessage = "View details in the extension!";

        if (report_status === leadReportStatusFailed) {
          notifTitle = `Research Failed for ${profileName}`;
          notifMessage = "Failed due to an unknown error.";
        }

        createNotification(tabId, notifTitle, notifMessage);
      }
      // Delete alarm.
      clearAlarm(tabId);

      console.log("deleted alarm for tab: ", tabId);
    }
  });
}

// Check if lead report exists for this linkedin person profile and save the result to storage as profile of the lead.
// Called when a new profile is detected in the tab or when we periodically check status of a lead report's status (upon start research).
function checkLeadReportForGivenProfile(
  profileName,
  linkedInProfileUrl,
  tabId
) {
  const encodedProfileURL = encodeURIComponent(linkedInProfileUrl);
  getUserObj().then((user) => {
    if (user === null) {
      // User not logged in, do nothing.
      console.log(
        `User not logged in, cannot check lead report in tab Id: ${tabId} for profile: ${linkedInProfileUrl}`
      );
      return;
    }
    user
      .getIdToken()
      .then((idToken) =>
        fetch(
          `${process.env.REACT_APP_API_HOSTNAME}/api/v1/lead-research-reports?url=${encodedProfileURL}`,
          {
            headers: { Authorization: "Bearer " + idToken },
          }
        )
      )
      .then((response) => response.json())
      .then((result) => {
        if (result.status === "error") {
          console.error(
            `Checking if LinkedIn profile exists failed with result: ${result}`
          );
          return;
        }

        // Create lead profile from the result. It will override any existing profile
        // whenver the existing LinkedIn profile in the current tab is changed.
        // We will delete this key when the tab is closed in the listener.
        createLeadProfile(
          tabId,
          profileName,
          linkedInProfileUrl,
          result.report_exists ? result.lead_research_report : null
        );
      });
  });
}

// Helper that returns true if this is a LinkedIn activity URL and false otherwise.
function isLinkedInRecentActivityURL(url) {
  return url.includes("linkedin.com/in/") && url.includes("recent-activity");
}

// Returns LinkedIn profile username from given LinkedIn activity URL.
// Returns null if username not found.
function getUsernameFromRecentActivityURL(url) {
  const urlElements = url.split("/");
  for (let idx = 0; idx < urlElements.length - 1; idx++) {
    const urlElem = urlElements[idx];
    if (urlElem.trim() === "in") {
      // The next one should be username.
      return urlElements[idx + 1].trim();
    }
  }
  console.error("Username not found for activity URL: ", url);
  return null;
}

// Handle tab updates to know when LinkedIn URL has changed. This change is then
// passed to Content Script which can then parse the URL and return whether it is valid or not.
// We need to pass to the Content Script since service worker does not have access
// to the DOM for the specific tab.
tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  const url = tab.url;
  if (isLinkedInRecentActivityURL(url) && changeInfo.status === "complete") {
    getActivityData(tabId).then((activityData) => {
      if (activityData !== null) {
        console.log("Fetch recent activity in URL: ", url);
        // We are in a state to fetch research activity from current tab.
        fetchCurrentActivityHTML(tabId).then((complete) => {
          if (complete) {
            // Create report.
            createLeadReport(tabId);

            // Send event.
            captureEvent("extension_create_report_called");
          }
        });
      } else {
        console.log("Fetch profile from backend for URL: ", url);
        // New URL in this tab, confirm and refetch profile.
        tabs
          .sendMessage(tabId, { action: "linkedin-profile-detected" })
          .then((profileDetails) => {
            if (profileDetails === null) {
              console.error("profile details not found for URL: ", url);
              // Do nothing.
              return;
            }

            // Send event.
            captureEvent("extension_lead_linkedin_profile_found", {
              profile_url: url,
            });

            checkLeadReportForGivenProfile(
              profileDetails.name,
              profileDetails.profileURL,
              tabId
            );
          });
      }
    });
  } else {
    // This else case is triggered even when LinkedIn profile is still loading and hasn't completed.
    // Delete existing lead profile from storage and delete any alarms if tab URL has changed.
    // User should not see past profile in popup if tab is not that of a lead profile.
    getTabData(tabId).then((data) => {
      if (data === null) {
        // No tab data found.
        return;
      }

      if (
        isLinkedInRecentActivityURL(url) &&
        getUsernameFromRecentActivityURL(data.url) ===
          getUsernameFromRecentActivityURL(url)
      ) {
        // Do nothing since it is the same profile so even if the URLs are different, we shouldn't clear the data.
        // We also delete any alarms that exist.
        return;
      }

      // Current tab's URL is different from stored lead's recent activity URL/
      // We should delete existing stored data in the tab and refecth new information.
      clearTabData(tabId);

      // Delete alarms if any.
      clearAlarm(tabId);
    });
  }
});

// Create Lead report using tabId that contains Lead's LinkedIn URL.
// Must not be called when activity research is in progress, only after
// research is complete.
function createLeadReport(tabId) {
  // Create lead research report in userport backend.
  getTabData(tabId).then((data) => {
    if (data === null) {
      console.error(
        "Cannot create lead report in tab ID: ",
        tabId,
        " because tab data is null (unexpected)!"
      );
      return;
    }

    const profileName = data.name;
    const linkedInProfileUrl = data.url;
    const postsHTML = getPostsActivityData(data.activityData);
    const commentsHTML = getCommentsActivityData(data.activityData);
    const reactionsHTML = getReactionsActivityData(data.activityData);
    getUserObj().then((user) => {
      if (user === null) {
        console.log(
          `User not logged in, cannot create report in tab Id: ${tabId}`
        );
        return;
      }

      user
        .getIdToken()
        .then((idToken) =>
          fetch(
            `${process.env.REACT_APP_API_HOSTNAME}/api/v1/lead-research-reports`,
            {
              method: "POST",
              body: JSON.stringify({
                linkedin_url: linkedInProfileUrl,
                origin: callOrigin,
                postsHTML: postsHTML,
                commentsHTML: commentsHTML,
                reactionsHTML: reactionsHTML,
              }),
              headers: {
                "Content-Type": "application/json",
                Authorization: "Bearer " + idToken,
              },
            }
          )
        )
        .then((response) => response.json())
        .then((result) => {
          if (result.status === "error") {
            console.error(
              `Failed to create report for linkedin URL: ${linkedInProfileUrl}`
            );
            return;
          }

          // Create leadProfile from the result and store it in the database.
          // This will also start an alarm if report status is not completed or failed.
          // It will also delete activity data that exists in the database automatically.
          createLeadProfile(
            tabId,
            profileName,
            linkedInProfileUrl,
            result.lead_research_report
          );
        });
    });
  });
}

// Handler for fire alarm events.
alarms.onAlarm.addListener((alarm) => {
  console.log("alarm fired with name: ", alarm.name);
  const tabId = tabIdKeyToNumber(alarm.name);
  getTabData(tabId).then((data) => {
    if (data === null) {
      // Clear alarm since there is no data associated with this alarm.
      // Return immmediately since no need to call backend.
      clearAlarm(tabId);
      return;
    }
    // Check report status in the backend. We will just reuse method that is used to
    // check if linkedin URL has a report or not and extract status from it.
    checkLeadReportForGivenProfile(data.name, data.url, tabId);
  });
});

// List to messages from Popup App. Usually these are user actions.
runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "fetch-user") {
    // Fetch user object from auth module and return to the caller.
    getUserObj().then((user) => sendResponse(user));

    // Since the user fetch is asynchronous, we return true;
    // Reference: https://developer.chrome.com/docs/extensions/develop/concepts/messaging.
    return true;
  }
  if (request.action === "fetch-lead-profile") {
    console.log("Popup requests lead profile on tab: ", request.tabId);

    getTabData(request.tabId).then((leadProfile) => sendResponse(leadProfile));

    // Since the lead profile fetch is asynchronous, we return true.
    return true;
  }
  if (request.action === "login-user") {
    startLogin(request);
    return;
  }

  if (request.action === "create-lead-report") {
    // Send event.
    captureEvent("extension_start_research_btn_clicked");

    // Start activity research first.
    const tabId = request.tabId;
    startActivityResearch(tabId)
      .then(() => fetchCurrentActivityHTML(tabId))
      .then((complete) => {
        if (complete) {
          // Create report.
          createLeadReport(tabId);

          // Send event.
          captureEvent("extension_create_report_called");
        }
      });

    // TODO: Update this to reflect activity research.
    sendResponse("new");

    // Sync response, return false.
    return false;
  }

  if (request.action === "view-lead-report") {
    // Navigate user to new tab to view the lead report in the Userport UI.

    // Send event.
    captureEvent("extension_view_report_btn_clicked");

    tabs.create({
      url: `${process.env.REACT_APP_HOSTNAME}/lead-research-reports/${request.report_id}`,
      active: true,
    });
    return;
  }

  if (request.action === "view-all-leads") {
    // Navigate user to new tab to view all the leads they have researched so far in the Userport UI.

    // Send event.
    captureEvent("extension_view_all_leads_btn_clicked");

    tabs.create({
      url: `${process.env.REACT_APP_HOSTNAME}/leads`,
      active: true,
    });
    return;
  }

  if (request.action === "logout-user") {
    // Send event.
    captureEvent("extension_logged_out");

    logOut().then(() => {
      console.log("User logged out");
      sendResponse(true);
    });

    // Async response, return true;
    return true;
  }
});

// Handle state for when user closes a tab. Usually a clean up of state is needed.
tabs.onRemoved.addListener(async (tabId, removeInfo) => {
  const userLoggingIn = await isUserLoggingIn(tabId);
  if (userLoggingIn) {
    handleLoginTabClosed();
    return;
  }

  // Handle clean up in this tab since user has closed it.
  const data = await getTabData(tabId);
  if (data !== null) {
    // Tab with LinkedIn profile is shut down. Clear any stored state in this tab.
    clearTabData(tabId);

    // Delete any alarms associated with this tab as well.
    clearAlarm(tabId);
  }
});
