/*global chrome*/
import "./main.css";
import { Typography, Button } from "antd";

const { Text, Link } = Typography;

// Component that displays based on research status.
function ResearchStatus({ researchStatus }) {
  if (researchStatus === "not_started") {
    return <Button className="action-btn">Start Research</Button>;
  }
  if (researchStatus === "complete") {
    return <Button className="action-btn">Research Report</Button>;
  }
  if (researchStatus === "in_progress") {
    return (
      <Button disabled className="action-btn">
        {" "}
        Research In Progress
      </Button>
    );
  }
  if (researchStatus === "failed_with_errors") {
    return (
      <Button disabled className="action-btn">
        Research Failed
      </Button>
    );
  }
}

// Component that displays whether lead research is possible or not
// depending on whether LinkedIn profile URL exists or not.
function LeadResearch({ linkedinProfileUrl, researchStatus }) {
  if (linkedinProfileUrl === null) {
    return (
      <div id="instructions-text-container">
        <Text id="instructions-text">LinkedIn profile not detected.</Text>
      </div>
    );
  }
  const profileDisplayText = linkedinProfileUrl.split("/in/")[1];
  return (
    <>
      <div id="instructions-text-container">
        <Text id="profile-detected-text">LinkedIn profile detected</Text>
        <Link id="profile-url" href={linkedinProfileUrl}>
          {profileDisplayText}
        </Link>
      </div>
      <ResearchStatus researchStatus={researchStatus} />
    </>
  );
}

// User Logged in component.
function Main({ linkedinProfileUrl, researchStatus }) {
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
        <LeadResearch
          linkedinProfileUrl={linkedinProfileUrl}
          researchStatus={researchStatus}
        />
        <Button className="action-btn" onClick={handleViewLeadReportsClick}>
          All Leads
        </Button>
      </div>
    </div>
  );
}

export default Main;
