import {
  runtime,
  tabs,
  storage,
  alarms,
  notifications,
} from "webextension-polyfill";
import {
  handleLoginTabClosed,
  isUserLoggingIn,
  logOut,
  startLogin,
} from "./login";
import { getUserObj } from "./auth";
import { captureEvent } from "./metrics";

// Module constants.
const leadReportStatusSuccess = "complete";
const leadReportStatusFailed = "failed_with_errors";
const callOrigin = "extension";

// Returns lead profile from storage. Returns null if it does not exist.
async function getLeadProfile(tabId) {
  const tabIdKey = tabId.toString();
  const item = await storage.local.get([tabIdKey]);
  if (tabIdKey in item) {
    return item[tabIdKey];
  }
  // User object does not exist (likely because this tab does not currently have a valid LinkedIn profile), return null.
  return null;
}

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
  const tabIdKey = tabId.toString();

  // If report status is not complete or failed, then create an alarm to poll status periodically.
  const report_status = lead_research_report
    ? lead_research_report.status
    : null;
  if (
    report_status &&
    report_status !== leadReportStatusSuccess &&
    report_status !== leadReportStatusFailed
  ) {
    // Create an alarm to poll report status and use tabId as key so that it is unique to a given tab.
    alarms.create(tabIdKey, { periodInMinutes: 1 });
  } else {
    // If there are any alarms for this tab, then it means users are waiting
    // for the result of research. We should present a notification if so.
    alarms.get(tabIdKey).then((item) => {
      if (item !== undefined && "name" in item) {
        // This is indeed a non empty 'alarm' object.
        var notifTitle = `Research Complete for ${profileName}`;
        var notifMessage = "View details in the extension!";

        if (report_status === leadReportStatusFailed) {
          notifTitle = `Research Failed for ${profileName}`;
          notifMessage = "Failed due to an unknown error.";
        }

        notifications.create(tabIdKey, {
          type: "basic",
          title: notifTitle,
          message: notifMessage,
          iconUrl: runtime.getURL("logo256.png"),
        });
        // Delete alarm.
        alarms.clear(tabIdKey);
      }
    });
  }

  // Add profile to storage.
  storage.local.set({ [tabIdKey]: leadProfile });
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

// Handle tab updates to know when LinkedIn URL has changed. This change is then
// passed to Content Script which can then parse the URL and return whether it is valid or not.
// We need to pass to the Content Script since service worker does not have access
// to the DOM for the specific tab.
tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  const url = tab.url;
  if (
    url.includes("linkedin.com/in/") &&
    url.includes("recent-activity") &&
    !url.includes("?") &&
    changeInfo.status === "complete"
  ) {
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
  } else {
    // This else case is triggered even when LinkedIn profile is still loading and hasn't completed.
    // Delete existing lead profile from storage and delete any alarms if tab URL has changed.
    // User should not see past profile in popup if tab is not that of a lead profile.
    const tabIdKey = tabId.toString();
    storage.local.get([tabIdKey]).then((item) => {
      if (tabIdKey in item) {
        const leadProfile = item[tabIdKey];
        if (leadProfile.url !== url) {
          // New URL detected that is not a Lead profile, delete existing lead profile from storage.
          storage.local.remove([tabIdKey]);
          // Delete alarms if any.
          alarms.clear(tabIdKey);
        }
      }
    });
  }
});

// Create Lead report using tabId that contains Lead's LinkedIn URL.
function createLeadReport(tabId, sendResponse) {
  // Create lead research report in userport backend.
  const tabIdKey = tabId.toString();
  storage.local.get(tabIdKey).then((item) => {
    if (tabIdKey in item) {
      const profileName = item[tabIdKey].name;
      const linkedInProfileUrl = item[tabIdKey].url;

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
                  postsHTML: null,
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
              // Send back null report status.
              sendResponse(null);
              return;
            }

            // Create leadProfile from the result and store it in the database.
            // This will also start an alarm if report status is not completed or failed.
            createLeadProfile(
              tabId,
              profileName,
              linkedInProfileUrl,
              result.lead_research_report
            );
            // Return status of report.
            sendResponse(result.lead_research_report.status);
          });
      });
    }
  });
}

// Alarm that handles
alarms.onAlarm.addListener((alarm) => {
  console.log("alarm fired with name: ", alarm.name);
  const tabIdKey = alarm.name;
  storage.local.get([tabIdKey]).then((item) => {
    if (tabIdKey in item) {
      const leadProfile = item[tabIdKey];
      // Check report status in the backend. We will just reuse method that is used to
      // check if linkedin URL has a report or not and extract status from it.
      checkLeadReportForGivenProfile(
        leadProfile.name,
        leadProfile.url,
        Number(tabIdKey)
      );
    } else {
      // Clear alarm since there is no lead profile associated with this alarm.
      alarms.clear(tabIdKey);
    }
  });
});

// Handle messages from Popup App and Content Script.
runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "fetch-user") {
    // Fetch user object from auth module and return to the caller.
    getUserObj().then((user) => sendResponse(user));

    // Since the user fetch is asynchronous, we return true;
    // Reference: https://developer.chrome.com/docs/extensions/develop/concepts/messaging.
    return true;
  }
  if (request.action === "fetch-lead-profile") {
    getLeadProfile(request.tabId).then((leadProfile) =>
      sendResponse(leadProfile)
    );

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

    createLeadReport(request.tabId, sendResponse);

    // Async response, return true.
    return true;
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
  const tabIdKey = tabId.toString();
  const item = await storage.local.get([tabIdKey]);
  if (item && tabIdKey in item) {
    // Tab with LinkedIn profile is shut down. Clear any stored state in this tab.
    storage.local.remove([tabIdKey]);

    // Delete any alarms associated with this tab as well.
    alarms.clear(tabIdKey);
  }
});
