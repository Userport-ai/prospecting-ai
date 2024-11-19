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
          <Text className="report-dates-label">Created On: </Text>
          <Text className="report-dates-value">
            {report.report_creation_date_readable_str}
          </Text>
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

  //  Older method to show team members.
  function PotentialTeamMembers() {
    if (
      report.insights.mentioned_team_members === null ||
      report.insights.mentioned_team_members.length === 0
    ) {
      return null;
    }
    return (
      <div id="mentioned-team-members">
        <Text className="title-text">Engagement with colleagues:</Text>
        <div>
          {report.insights.mentioned_team_members.map((memberInfo) => {
            const displayName = memberInfo.name + `-${memberInfo.count}`;
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

  //  Older method to show product associations.
  function PotentialProductAssociations() {
    if (
      report.insights.potential_product_associations === null ||
      report.insights.potential_product_associations.length === 0
    ) {
      return null;
    }
    return (
      <div id="potential-product-associations">
        <Text className="title-text">Engagement with Products:</Text>
        <div>
          {report.insights.potential_product_associations.map((productInfo) => {
            const displayName = productInfo.name + `-${productInfo.count}`;
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

  // Description of their Personality.
  function PersonalityDescription() {
    if (report.insights.personality_description === null) {
      return null;
    }
    return (
      <div id="personality-description">
        <Text className="insight-label">Personality</Text>
        <Text className="insight-text">
          {report.insights.personality_description}
        </Text>
      </div>
    );
  }

  // Description of their areas of interest.
  function AreasOfInterest() {
    if (
      report.insights.areas_of_interest === null ||
      report.insights.areas_of_interest.interests === null ||
      report.insights.areas_of_interest.interests.length === 0
    ) {
      return null;
    }

    return (
      <div id="areas-of-interest">
        <Text className="insight-label">Areas of Interest</Text>
        <div id="all-interests-container">
          {report.insights.areas_of_interest.interests.map((interest) => {
            if (interest.description) {
              return (
                <div key={interest.description} className="interest-container">
                  <Text className="interest-description">
                    {interest.description}
                  </Text>
                  <Text className="interest-reason">{interest.reason}</Text>
                </div>
              );
            }
          })}
        </div>
      </div>
    );
  }

  // Stats related to number of company-related posts the lead has engaged with.
  function CompanyPostsStats() {
    if (
      report.insights.num_company_related_activities === null ||
      report.insights.total_engaged_activities === null ||
      report.insights.total_engaged_activities === 0
    ) {
      return null;
    }

    return (
      <div id="company-posts-engagement-stats">
        <Text className="insight-label">
          Engagement with {report.company_name}'s posts
        </Text>
        <Text className="insight-text">
          {report.person_name} has engaged with{" "}
          {report.insights.num_company_related_activities} posts related to{" "}
          {report.company_name} out of the{" "}
          {report.insights.total_engaged_activities} posts they have engaged
          with.
        </Text>
      </div>
    );
  }

  // List of colleagues they have engaged with on LinkedIn posts.
  function EngagedColleagues() {
    if (report.insights.engaged_colleagues === null) {
      return null;
    }

    var engagedColleagues = "None";
    if (report.insights.engaged_colleagues.length > 0) {
      engagedColleagues = report.insights.engaged_colleagues.join(", ");
    }

    return (
      <div id="engaged-colleagues">
        <Text className="insight-label">Engagement with Colleagues</Text>
        <Text className="insight-text">{engagedColleagues}</Text>
      </div>
    );
  }

  // List of products they have engaged with on LinkedIn posts.
  function EngagedProducts() {
    if (report.insights.engaged_products === null) {
      return null;
    }

    var engagedProducts = "None";
    if (report.insights.engaged_products.length > 0) {
      engagedProducts = report.insights.engaged_products.join(", ");
    }

    return (
      <div id="engaged-colleagues">
        <Text className="insight-label">
          Engagement with {report.company_name}'s Products
        </Text>
        <Text className="insight-text">{engagedProducts}</Text>
      </div>
    );
  }

  return (
    <div id="report-insights">
      <PersonalityDescription />
      <AreasOfInterest />
      <CompanyPostsStats />
      <EngagedColleagues />
      <EngagedProducts />
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

  // TODO: Remove this once we know if we are only using LinkedIn activity or combined
  // Activity + web results for outreach.
  const tabHeading =
    report.research_request_type === "linkedin_only"
      ? "Recent Activity"
      : "Recent News";

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
              label: <h1>{tabHeading}</h1>,
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
