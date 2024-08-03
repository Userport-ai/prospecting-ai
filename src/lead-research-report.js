import "./lead-research-report.css";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { Flex, Typography, Button, Card } from "antd";
import { useNavigate, useLoaderData } from "react-router-dom";
import { useState } from "react";
import { sampleReport, outreachMessages } from "./lead-result-data";

const { Title, Text } = Typography;

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
      <Text className="card-text">{highlight.concise_summary}</Text>
      <div>
        <Button className="card-citation-link" type="link" href={highlight.url}>
          {highlight.url}
        </Button>
      </div>
      <Text className="card-date">{highlight.publish_date_readable_str}</Text>
    </Card>
  );
}

function DetailSection({ detail }) {
  const [cardClicked, setCardClicked] = useState(false);
  return (
    <>
      <Button
        className="detail-section-btn"
        type="primary"
        onClick={() => setCardClicked(!cardClicked)}
      >
        {detail.category_readable_str}
      </Button>
      {cardClicked &&
        detail.highlights.map((highlight) => (
          <HighlightCard key={highlight.url} highlight={highlight} />
        ))}
    </>
  );
}

// Loader to fetch research report for given lead.
export async function leadResearchReportLoader({ params }) {
  // const response = await fetch("/api/v1/lead-research-reports/" + params.id);
  // const result = await response.json();
  const result = await sampleReport;
  if (result.status === "error") {
    console.log("Error getting lead report: ", result);
    throw result;
  }
  return result;
}

function LeadResearchReport() {
  const navigate = useNavigate();
  const report = useLoaderData();

  return (
    <div id="lead-result-outer">
      <div id="lead-result-container">
        <ArrowLeftOutlined onClick={() => navigate("/")} />
        <Flex vertical={true} align="flex-start">
          <Title level={3}>
            {report.person_name}, {report.person_role_title},{" "}
            {report.company_name}
          </Title>
          <Button type="link" href={report.linkedin_url}>
            {report.linkedin_url}
          </Button>
        </Flex>

        <Flex id="info-container" vertical={true} gap="large">
          {report.details.map((detail) => (
            <DetailSection key={detail.category} detail={detail} />
          ))}
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
