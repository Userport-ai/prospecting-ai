import "./lead-research-report.css";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { Flex, Typography, Button, Card, Spin } from "antd";
import {
  useNavigate,
  useLoaderData,
  useNavigation,
  redirect,
} from "react-router-dom";
import { useState } from "react";
import { sampleReport, outreachMessages } from "./lead-research-report-data";

const { Title, Text, Link } = Typography;

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

function OutreachCard({ text }) {
  return (
    <Card>
      <Text className="outreach-text">{addLineBreaks(text)}</Text>
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

// Loader to fetch research report for given lead.
export const leadResearchReportLoader = (authContext) => {
  return async ({ params }) => {
    const { user } = authContext;
    if (!user) {
      // User is logged out.
      return redirect("/login");
    }
    const response = await fetch("/api/v1/lead-research-reports/" + params.id, {
      headers: { Authorization: "Bearer " + user.accessToken },
    });
    const result = await response.json();
    // const result = await sampleReport;
    if (result.status === "error") {
      console.log("Error getting lead report: ", result);
      throw result;
    }
    return result.lead_research_report;
  };
};

function LeadResearchReport() {
  const navigate = useNavigate();
  const report = useLoaderData();
  const navigation = useNavigation();
  const loading_or_submitting = navigation.state !== "idle";

  return (
    <div id="lead-research-report-outer">
      <div id="lead-research-report-container">
        <Spin spinning={loading_or_submitting} />;
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
              <Text>Report Creation Date: </Text>
              <Text strong>{report.report_creation_date_readable_str}</Text>
            </div>
            <div id="research-start-date">
              <Text>Research Start Date: </Text>
              <Text strong>
                {" "}
                {report.report_publish_cutoff_date_readable_str}
              </Text>
            </div>
          </div>
        </div>
        <Flex id="report-details-container" vertical={false} wrap gap="large">
          <CategoriesSection report={report} />
        </Flex>
        <Flex id="outreach-container" vertical={true} gap="large">
          <Title level={4}>Sample Outreach Messages</Title>
          <OutreachCard key="1" text={outreachMessages[0]} />
          <OutreachCard key="2" text={outreachMessages[1]} />
        </Flex>
      </div>
    </div>
  );
}

export default LeadResearchReport;
