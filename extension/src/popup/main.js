/*global chrome*/
import "./main.css";
import { Typography, Button, Modal } from "antd";
import { useEffect, useState } from "react";

const { Text, Link } = Typography;

// Get current tab of the popup.
async function getCurrentTab() {
  let queryOptions = { active: true, lastFocusedWindow: true };
  // `tab` will either be a `tabs.Tab` instance or `undefined`.
  let [tab] = await chrome.tabs.query(queryOptions);
  if (tab === undefined) {
    console.error("Got undefined active tab, could not fetch lead profile.");
    return null;
  }
  return tab;
}

function ResearchReport({ lead_research_report }) {
  const initialReportStatus = lead_research_report
    ? lead_research_report.status
    : "not_started";
  const [reportStatus, setReportStatus] = useState(initialReportStatus);
  const [loading, setLoading] = useState(false);

  // Handle user click to view research report.
  function onViewReportClick() {
    // Chrome runtime exists only when called inside extension.
    if (chrome.runtime) {
      // Send message to service worker to view lead research report.
      chrome.runtime.sendMessage({
        action: "view-lead-report",
        report_id: lead_research_report.id,
      });
    }
  }

  // Handle user click to create report.
  async function onCreateReportClick() {
    const tab = await getCurrentTab();
    if (tab === null) {
      return;
    }
    if (chrome.runtime) {
      setLoading(true);
      // Send message to service worker to create lead research report.
      const leadReportStatus = await chrome.runtime.sendMessage({
        action: "create-lead-report",
        tabId: tab.id,
      });
      setLoading(false);
      if (!leadReportStatus) {
        Modal.error({
          title: "Research failed",
          content: "Due to an error, failed to start research",
        });
        return;
      }
      setReportStatus(leadReportStatus);
    }
  }

  if (reportStatus === "not_started") {
    return (
      <Button
        className="action-btn"
        loading={loading}
        disabled={loading}
        onClick={onCreateReportClick}
      >
        Start Research
      </Button>
    );
  }
  if (reportStatus === "complete") {
    return (
      <Button className="action-btn" onClick={onViewReportClick}>
        View Research Report
      </Button>
    );
  }
  if (reportStatus === "failed_with_errors") {
    return (
      <Button disabled className="action-btn">
        Research Failed
      </Button>
    );
  }

  // Any other status means report creation is still in progress.
  return (
    <Button disabled className="action-btn">
      {" "}
      Research In Progress
    </Button>
  );
}

// Component that displays user profile.
function LeadResearch({ leadProfile }) {
  if (leadProfile === null) {
    return (
      <div id="instructions-text-container">
        <Text id="instructions-text">
          LinkedIn profile not detected in this tab.
        </Text>
      </div>
    );
  }

  const linkedInProfileUrl = leadProfile.url;
  const profileDisplayText = linkedInProfileUrl.split("/in/")[1];
  return (
    <>
      <div id="instructions-text-container">
        <Text id="profile-detected-text">LinkedIn profile detected</Text>
        <Link id="profile-url" href={linkedInProfileUrl}>
          {profileDisplayText}
        </Link>
      </div>
      <ResearchReport lead_research_report={leadProfile.lead_research_report} />
    </>
  );
}

// User Logged in component.
function Main() {
  const [leadProfile, setLeadProfile] = useState(null);
  useEffect(() => {
    async function fetchLeadProfile() {
      // Chrome runtime exists only when called inside extension.
      if (chrome.runtime) {
        const tab = await getCurrentTab();
        if (tab === null) {
          return;
        }

        // Send message to service worker to get user state.
        const gotLeadProfile = await chrome.runtime.sendMessage({
          action: "fetch-lead-profile",
          tabId: tab.id,
        });
        setLeadProfile(gotLeadProfile);
      }
    }
    fetchLeadProfile();
  }, []);

  // Handle click by user to view all lead reports.
  function handleViewLeadReportsClick() {
    // Chrome runtime exists only when called inside extension.
    if (chrome.runtime) {
      // Send message to service worker to start login.
      chrome.runtime.sendMessage({ action: "view-all-leads" });
    }
  }
  return (
    <div id="main-outer-container">
      <div id="main-inner-container">
        <LeadResearch leadProfile={leadProfile} />
        <Button className="action-btn" onClick={handleViewLeadReportsClick}>
          View All Leads
        </Button>
      </div>
    </div>
  );
}

export default Main;
