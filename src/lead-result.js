import "./lead-result.css";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { Flex, Typography, Button } from "antd";
import { useNavigate } from "react-router-dom";

const { Title } = Typography;

function InfoSection({ sectionTitle }) {
  return (
    <Button className="info-section-btn" type="primary">
      {sectionTitle}
    </Button>
  );
}

function LeadResult() {
  const navigate = useNavigate();
  return (
    <div id="lead-result-outer">
      <div id="lead-result-container">
        <Flex vertical={false} gap="middle">
          <ArrowLeftOutlined onClick={() => navigate("/")} />
          <Title level={3}>Zach Perret, CEO, Plaid</Title>
        </Flex>
        <Flex id="info-container" vertical={true} gap="large">
          <InfoSection sectionTitle="About"></InfoSection>
          <InfoSection sectionTitle="Thoughts"></InfoSection>
          <InfoSection sectionTitle="Events Attended"></InfoSection>
          <InfoSection sectionTitle="Fundraise Announcements"></InfoSection>
          <InfoSection sectionTitle="Awards and Recognition"></InfoSection>
          <InfoSection sectionTitle="Company Announcements"></InfoSection>
          <InfoSection sectionTitle="Product Updates"></InfoSection>
        </Flex>
        <Flex id="outreach-container" vertical={true} gap="large">
          <Title level={4}>Outreach Messages</Title>
        </Flex>
      </div>
    </div>
  );
}

export default LeadResult;
