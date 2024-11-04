import "./lead-research-report.css";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { Typography, Tabs, Skeleton } from "antd";
import { useNavigate, useLoaderData, useNavigation } from "react-router-dom";
import { useContext, useState } from "react";
import { AuthContext } from "./root";
import {
  getUserFromServer,
  isUserOnboarding,
  stateAfterViewedPersonalizedEmails,
  updateUserStateOnServer,
  userHasNotViewedPersonalizedEmail,
} from "./helper-functions";
import PersonalizedEmails from "./personalized-emails";
import OnboardingProgressBar from "./onboarding-progress-bar";
import RecentNews from "./recent-news";
import { usePostHog } from "posthog-js/react";

const { Text, Link } = Typography;

// Header of the report. Contains information and insights about the lead.
function ReportHeader({ report }) {
  const navigate = useNavigate();
  const posthog = usePostHog();

  return (
    <div id="report-header">
      <div id="back-arrow">
        <ArrowLeftOutlined onClick={() => navigate("/")} />
      </div>
      <div id="person-details-container">
        <div id="person-details">
          <h1 id="person-name">{report.person_name}</h1>
          <h3 id="role-title">
            {report.person_role_title}, {report.company_name}
          </h3>
          <Link
            id="linkedin-url"
            href={report.person_linkedin_url}
            target="_blank"
            onClick={() => {
              // Send event.
              posthog.capture("report_header_linkedin_profile_clicked", {
                report_id: report.id,
              });
            }}
          >
            {report.person_linkedin_url}
          </Link>
        </div>
      </div>
      <div id="report-dates">
        <div id="report-creation-date">
          <Text className="report-dates-label">Report Creation Date: </Text>
          <Text strong>{report.report_creation_date_readable_str}</Text>
        </div>
        <div id="research-start-date">
          <Text className="report-dates-label">Research Start Date: </Text>
          <Text strong> {report.report_publish_cutoff_date_readable_str}</Text>
        </div>
      </div>
    </div>
  );
}

// Component to display lead and company insights in the appropriate format.
function Insights({ report }) {
  if (report.insights === null) {
    return null;
  }

  function PotentialTeamMembers() {
    if (
      report.insights.mentioned_team_members === null ||
      report.insights.mentioned_team_members.length === 0
    ) {
      return null;
    }
    return (
      <div id="mentioned-team-members">
        <Text className="title-text">Potential team members:</Text>
        <div>
          {report.insights.mentioned_team_members.map((memberInfo) => {
            const displayName = memberInfo.name;
            return (
              <Text key={displayName} className="value-text">
                {displayName}
              </Text>
            );
          })}
        </div>
      </div>
    );
  }

  function PotentialProductAssociations() {
    if (
      report.insights.potential_product_associations === null ||
      report.insights.potential_product_associations.length === 0
    ) {
      return null;
    }
    return (
      <div id="potential-product-associations">
        <Text className="title-text">Potential Products associatons:</Text>
        <div>
          {report.insights.potential_product_associations.map((productInfo) => {
            const displayName = productInfo.name;
            return (
              <Text key={displayName} className="value-text">
                {displayName}
              </Text>
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <div id="report-insights">
      <PotentialTeamMembers />
      <PotentialProductAssociations />
    </div>
  );
}

// Loader to fetch research report for given lead.
export const leadResearchReportLoader = (authContext) => {
  return async ({ params }) => {
    const { user } = authContext;
    if (!user) {
      // User is logged out.
      return null;
    }
    const idToken = await user.getIdToken();
    const response = await fetch("/api/v1/lead-research-reports/" + params.id, {
      headers: { Authorization: "Bearer " + idToken },
    });
    const result = await response.json();
    if (result.status === "error") {
      throw result;
    }
    return result;
  };
};

// Main Component.
function LeadResearchReport() {
  const loaderResponse = useLoaderData();
  const report = loaderResponse.lead_research_report;
  const [userFromServer, setUserFromServer] = useState(loaderResponse.user);
  const component_is_loading = useNavigation().state !== "idle";
  const { user } = useContext(AuthContext);
  const [activeTabKey, setActiveTabKey] = useState(recentNewsTabKey());
  const [personalizedEmails, setPersonalizedEmails] = useState(
    report.personalized_outreach_messages.personalized_emails
  );
  const posthog = usePostHog();

  if (component_is_loading) {
    return (
      <Skeleton
        active
        paragraph={{
          rows: 15,
        }}
      />
    );
  }

  // Helper to get tab key for Recent News tab.
  function recentNewsTabKey() {
    return "1";
  }

  // Helper to get tab key for Personalized Email tab.
  function personalizedEmailsTabKey() {
    return "2";
  }

  // Handler for when user changes tab.
  async function onActiveTabChange(activeKey) {
    if (
      activeKey !== recentNewsTabKey() &&
      activeKey !== personalizedEmailsTabKey()
    ) {
      const error_obj = {
        message: `Invalid Tab key value: ${activeKey}`,
        status_code: 500,
      };
      throw error_obj;
    }

    if (
      activeKey === personalizedEmailsTabKey() &&
      userHasNotViewedPersonalizedEmail(userFromServer.state)
    ) {
      // First time user is viewing personalized emails, update the user state on server and then the UI.
      // User is onboarded now.
      const idToken = await user.getIdToken();
      await updateUserStateOnServer(
        stateAfterViewedPersonalizedEmails(),
        idToken
      );
      const gotUserFromServer = await getUserFromServer(idToken);
      setUserFromServer(gotUserFromServer);
    }
    setActiveTabKey(activeKey);

    // Send event.
    const activeTabName =
      activeKey === recentNewsTabKey() ? "Recent News" : "Personalized Emails";
    posthog.capture("report_clicked_tab", {
      tab: activeTabName,
      report_id: report.id,
    });
  }

  // Handles successful personalized email creation by user.
  function handleEmailCreation(createdPersonalizedEmail) {
    // Add personalized email to existing list of personalized emails and switch the tab to personalized emails.
    setPersonalizedEmails([...personalizedEmails, createdPersonalizedEmail]);
    setActiveTabKey(personalizedEmailsTabKey());
  }

  return (
    <div id="lead-research-report-outer">
      {isUserOnboarding(userFromServer) && (
        <OnboardingProgressBar userFromServer={userFromServer} />
      )}
      <div id="lead-research-report-container">
        <ReportHeader report={report} />
        <Insights report={report} />
        <Tabs
          onChange={onActiveTabChange}
          activeKey={activeTabKey}
          items={[
            {
              label: <h1>Recent News</h1>,
              key: recentNewsTabKey(),
              children: (
                <RecentNews
                  lead_research_report_id={report.id}
                  details={report.details}
                  onEmailCreation={handleEmailCreation}
                />
              ),
            },
            {
              label: <h1>Personalized Emails</h1>,
              key: personalizedEmailsTabKey(),
              children: (
                <PersonalizedEmails
                  lead_research_report_id={report.id}
                  personalized_emails={personalizedEmails}
                />
              ),
            },
          ]}
        />
      </div>
    </div>
  );
}

export default LeadResearchReport;
