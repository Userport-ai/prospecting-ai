/*global chrome*/
import "./main.css";
import { Typography, Button, Modal } from "antd";
import { useEffect, useState } from "react";
import { mockLeadProfile } from "./mock";
import { getCurrentTab } from "./helper";

const { Text, Link } = Typography;

// Component to display outreach messages within the extension itself.
function PersonalizedOutreachMessages({ lead_research_report }) {
  if (
    lead_research_report === null ||
    lead_research_report.personalized_outreach_messages === null
  ) {
    // This can be the case when research has not started or it is in progress
    // and personalized messages have not been generated yet.
    return <div></div>;
  }

  const outreachMessages =
    lead_research_report.personalized_outreach_messages.personalized_emails.map(
      (email) => {
        return { text: email.email_opener, url: email.highlight_url };
      }
    );
  return (
    <div id="personalized-messages-container">
      <Text id="personalized-messages-title">Personalized Messages:</Text>
      {outreachMessages.map((message) => (
        <div className="single-message-container">
          <Text className="message-text">{message.text}</Text>
          <Text className="message-source">Source:</Text>
          <Link href={message.url} target="_blank" className="message-url">
            {message.url}
          </Link>
        </div>
      ))}
    </div>
  );
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

  // Handle user click to start research.
  async function onStartResearchClick() {
    if (chrome.runtime) {
      const tab = await getCurrentTab();
      if (tab === null) {
        return;
      }
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

  var reportStatusComp = null;
  var reportActionComp = null;
  if (reportStatus === "not_started") {
    reportStatusComp = <Text id="status-not-started">Not Started</Text>;
    reportActionComp = (
      <Button
        id="start-research-btn"
        loading={loading}
        disabled={loading}
        onClick={onStartResearchClick}
      >
        Start Research
      </Button>
    );
  } else if (reportStatus === "complete") {
    reportStatusComp = <Text id="status-complete">Ready</Text>;
    reportActionComp = (
      <Button id="view-report-btn" onClick={onViewReportClick}>
        View Full Report
      </Button>
    );
  } else if (reportStatus === "failed_with_errors") {
    reportStatusComp = <Text id="status-failed">Error</Text>;
  } else {
    // Any other status means report creation is still in progress.
    reportStatusComp = <Text id="status-in-progress">In Progress</Text>;
    reportActionComp = (
      <Text id="in-progress-notif">
        Research should complete in 5-10 minutes. Open the extension again after
        that. We will also send you a Chrome notification upon completion!
      </Text>
    );
  }

  return (
    <div id="report-container">
      <div id="report-status-container">
        <Text id="status-label">Research Status:</Text>
        {reportStatusComp}
      </div>
      <PersonalizedOutreachMessages
        lead_research_report={lead_research_report}
      />
      {reportActionComp}
    </div>
  );
}

// Component that displays lead profile.
function LeadProfile({ leadProfile }) {
  if (leadProfile === null) {
    return (
      <div id="instructions-text-container">
        <Text id="not-found-text">
          LinkedIn profile of a person not found in this tab. Try reloading the
          tab if you think this is the incorrect.
        </Text>
      </div>
    );
  }

  const linkedInProfileUrl = leadProfile.url;
  const profileDisplayText = linkedInProfileUrl.split("/in/")[1];
  return (
    <>
      <div id="profile-details-container">
        <Text id="profile-name">{leadProfile.name}</Text>
        <Link id="profile-url" href={linkedInProfileUrl}>
          {profileDisplayText}
        </Link>
      </div>
      <ResearchReport lead_research_report={leadProfile.lead_research_report} />
    </>
  );
}

// User Logged in component.
function Main({ handleLogout }) {
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
        <LeadProfile leadProfile={leadProfile} />
        <div id="other-actions-container">
          <Text className="other-actions-text">Other Actions:</Text>
          <Button className="action-btn" onClick={handleViewLeadReportsClick}>
            View All Leads
          </Button>
          <Button className="action-btn" onClick={handleLogout}>
            Log Out
          </Button>
        </div>
      </div>
    </div>
  );
}

export default Main;
