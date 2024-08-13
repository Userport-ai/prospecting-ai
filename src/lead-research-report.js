import "./lead-research-report.css";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { Flex, Typography, Button, Card, Spin, Tabs } from "antd";
import {
  useNavigate,
  useLoaderData,
  useNavigation,
  redirect,
} from "react-router-dom";
import { useState } from "react";
import { sampleReport, outreachMessages } from "./lead-research-report-data";

const { Text, Link } = Typography;

function addLineBreaks(text) {
  return text.split("\n").map((substr) => {
    return (
      <>
        {substr}
        <br />
      </>
    );
  });
}

function PersonalizedEmailCard({
  personalized_email,
  chosen_outreach_email_template,
}) {
  // TODO: Handle case when chosen outreach template is null.
  return (
    <Card>
      <div className="email-subject-container">
        <Text className="email-subject-label">Subject</Text>
        <Text className="email-subject-text">
          {personalized_email.email_subject_line}
        </Text>
      </div>
      <div className="email-body-container">
        <Text className="email-body-label">Body</Text>
        <Text className="outreach-text">
          {addLineBreaks(
            personalized_email.email_opener +
              "\n\n" +
              chosen_outreach_email_template.message
          )}
        </Text>
      </div>
    </Card>
  );
}

function PersonalizedEmails({ report }) {
  return (
    <div id="outreach-container">
      {report.personalized_emails.map((personalized_email) => (
        <PersonalizedEmailCard
          personalized_email={personalized_email}
          chosen_outreach_email_template={report.chosen_outreach_email_template}
        />
      ))}
    </div>
  );
}

function SelectedOutreachEmailTemplate({ report }) {
  return (
    <Card id="email-template-card">
      <div id="template-message-container">
        <Text className="card-text-label" strong>
          Message
        </Text>
        <Text id="template-message-text">
          {addLineBreaks(report.chosen_outreach_email_template.message)}
        </Text>
      </div>
    </Card>
  );
}

function HighlightCard({ highlight }) {
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

function CategoriesSection({ report }) {
  var initialSelectedCategories = [];
  if (report.details.length > 0) {
    initialSelectedCategories = [report.details[0].category_readable_str];
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
      {report.details.map((detail) => {
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
            report.details.filter(
              (detail) => detail.category_readable_str === selectedCategory
            )[0]
        )
        .flatMap((detail) =>
          detail.highlights.map((highlight) => (
            <HighlightCard highlight={highlight} />
          ))
        )}
    </>
  );
}

function RecentNews({ report }) {
  return (
    <Flex id="report-details-container" vertical={false} wrap gap="large">
      <CategoriesSection report={report} />
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
      return redirect("/login");
    }
    // const response = await fetch("/api/v1/lead-research-reports/" + params.id, {
    //   headers: { Authorization: "Bearer " + user.accessToken },
    // });
    // const result = await response.json();
    const result = await sampleReport;
    if (result.status === "error") {
      console.log("Error getting lead report: ", result);
      throw result;
    }
    return result.lead_research_report;
  };
};

// Main Component.
function LeadResearchReport() {
  const report = useLoaderData();
  const navigation = useNavigation();
  const loading_or_submitting = navigation.state !== "idle";

  return (
    <div id="lead-research-report-outer">
      <div id="lead-research-report-container">
        <Spin spinning={loading_or_submitting} />;
        <ReportHeader report={report} />
        <Tabs
          items={[
            {
              label: <h1>Recent News</h1>,
              key: 1,
              children: <RecentNews report={report} />,
            },
            {
              label: <h1>Email Template</h1>,
              key: 2,
              children: <SelectedOutreachEmailTemplate report={report} />,
            },
            {
              label: <h1>Personalized Emails</h1>,
              key: 3,
              children: <PersonalizedEmails report={report} />,
            },
          ]}
        />
      </div>
    </div>
  );
}

export default LeadResearchReport;
