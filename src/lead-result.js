import "./lead-result.css";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { Flex, Typography, Button, Card } from "antd";
import { useNavigate } from "react-router-dom";

const { Title, Text } = Typography;

const outreachTextOne =
  "Hi Zachary, Congrats on Plaid being named #1 for the Finance category of Most Innovative Companies for 2024! \
  It’s great to see new features via RTP & FedNow while keeping the ecosystem safe at the same time with anti-fraud tools like Signal!";

const outreachTextTwo =
  "Hi Zachary, Congrats on the recent launch of Plaid Layer! \
It’s so cool that you can verify a user’s identity just by using their phone number using Layer and also improve user conversion rates by nearly 90%. ";

function InfoCard({ text }) {
  return (
    <Card>
      <Text>{text}</Text>
    </Card>
  );
}

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
          <Title level={4}>Sample Outreach Messages</Title>
          <InfoCard text={outreachTextOne} />
          <InfoCard text={outreachTextTwo} />
        </Flex>
      </div>
    </div>
  );
}

export default LeadResult;
