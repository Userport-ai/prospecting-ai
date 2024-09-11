import "./lead-research-report.css";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { Flex, Typography, Button, Card, Tabs, Skeleton } from "antd";
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

const { Text, Link } = Typography;

// Represents Highlight from the leads' news.
function Highlight({ highlight }) {
  return (
    <Card>
      <div>
        <Text strong className="card-category">
          {highlight.category_readable_str}
        </Text>
      </div>
      <div className="card-citation-link-container">
        <Text className="card-citation-source-label" strong>
          Source:{" "}
        </Text>
        <Link
          className="card-citation-link"
          href={highlight.url}
          target="_blank"
        >
          {highlight.url}
        </Link>
      </div>
      <div className="card-date-container">
        <Text className="card-date-label" strong>
          Publish Date:{" "}
        </Text>
        <Text className="card-date">{highlight.publish_date_readable_str}</Text>
      </div>
      <div className="card-text-container">
        <Text className="card-text-label" strong>
          Summary
        </Text>
        <Text className="card-text">{highlight.concise_summary}</Text>
      </div>
    </Card>
  );
}

// Represents Categories buttons and associated highlights.
function CategoriesAndHighlights({ details }) {
  var initialSelectedCategories = [];
  if (details.length > 0) {
    initialSelectedCategories = [details[0].category_readable_str];
  }
  const [categoriesSelected, setCategoriesSeleted] = useState(
    initialSelectedCategories
  );

  function handleCategoryClicked(category) {
    if (categoriesSelected.filter((cat) => cat === category).length === 0) {
      // Category not selected yet, prepend to selection.
      setCategoriesSeleted([category, ...categoriesSelected]);
    } else {
      // Category already selected, remove it.
      setCategoriesSeleted(
        categoriesSelected.filter((cat) => cat !== category)
      );
    }
  }

  return (
    <>
      {/* These are the categories */}
      {details.map((detail) => {
        let categoryBtnClass = categoriesSelected.includes(
          detail.category_readable_str
        )
          ? "category-btn-selected"
          : "category-btn";
        return (
          <Button
            key={detail.category}
            className={categoryBtnClass}
            type="primary"
            onClick={(e) => handleCategoryClicked(e.target.innerText)}
          >
            {detail.category_readable_str}
          </Button>
        );
      })}
      {/* These are the highlights from selected categories. */}
      {categoriesSelected
        .map(
          (selectedCategory) =>
            // Filtered category guaranteed to exist and size 1 since selected categories
            // are from the same details array.
            details.filter(
              (detail) => detail.category_readable_str === selectedCategory
            )[0]
        )
        .flatMap((detail) =>
          detail.highlights.map((highlight) => (
            <Highlight key={highlight.id} highlight={highlight} />
          ))
        )}
    </>
  );
}

function RecentNews({ details }) {
  return (
    <Flex id="report-details-container" vertical={false} wrap gap="large">
      <CategoriesAndHighlights details={details} />
    </Flex>
  );
}

function ReportHeader({ report }) {
  const navigate = useNavigate();
  return (
    <div id="header">
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
      console.log("Error getting lead report: ", result);
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
  }

  return (
    <div id="lead-research-report-outer">
      {isUserOnboarding(userFromServer) && (
        <OnboardingProgressBar userFromServer={userFromServer} />
      )}
      <div id="lead-research-report-container">
        <ReportHeader report={report} />
        <Tabs
          onChange={onActiveTabChange}
          items={[
            {
              label: <h1>Recent News</h1>,
              key: recentNewsTabKey(),
              children: <RecentNews details={report.details} />,
            },
            {
              label: <h1>Personalized Emails</h1>,
              key: personalizedEmailsTabKey(),
              children: (
                <PersonalizedEmails
                  lead_research_report_id={report.id}
                  personalized_emails={
                    report.personalized_outreach_messages.personalized_emails
                  }
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
