import "./lead-result.css";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { Flex, Typography, Button, Card } from "antd";
import { useNavigate } from "react-router-dom";
import { useState } from "react";

const { Title, Text } = Typography;

const outreachMessages = [
  "Hi Zachary, Congrats on Plaid being named #1 for the Finance category of Most Innovative Companies for 2024! \
  It’s great to see new features via RTP & FedNow while keeping the ecosystem safe at the same time with anti-fraud tools like Signal!",
  "Hi Zachary, Congrats on the recent launch of Plaid Layer! \
It’s so cool that you can verify a user’s identity just by using their phone number using Layer and also improve user conversion rates by nearly 90%. ",
];

const aboutPerson = {
  text: "Zacahary is the CEO and Cofounder of Plaid. He cofounded the company 12 years ago in 2012. He studied at Duke university and worked at Bain & Company before that.",
  citationLink: "https://www.linkedin.com/in/zach-perret",
};

const thoughts = {
  text: "While introducing Plaid Consumer report he said, 'Credit underwriting in the US is broken. Too much paperwork, incomplete data, thin files, and many of the crucial consumer factors are not considered. Excited to be taking a first step towards fixing it'",
  citationLink:
    "https://www.linkedin.com/posts/zperret_introducing-consumer-report-a-new-solution-activity-7203797435322621953-mbS6",
};

const events = {
  text: "Talked about talking at Plaid's annual conference Plaid Effects. He said, 'This coming Tuesday, during Plaid Effects, we'll be sharing our latest product releases that are helping our customers onboard users faster, lower costs of payments and approve more borrowers while reducing risk.\
        We will also welcome guests from industry leaders like Coinbase, H&R Block and Adyen, who will share how they’re using Plaid to move the industry forward.'",
  citationLink:
    "https://www.linkedin.com/posts/zperret_effects-2024-activity-7207132820387893248--1N-/",
};

const fundraise = {
  text: "Plaid has recently been in the news due to significant financial activity. As of June 2024, Plaid is raising funds at a valuation of $15 billion. This news comes as employees were offered shares at $1,200 each, indicating strong investor confidence in the company's future prospects. The fundraising efforts are part of Plaid's strategy to expand its financial technology services and continue its growth trajectory​.",
  citationLink:
    "https://www.fintechfutures.com/2021/01/plaid-raising-at-15bn-as-employees-pitched-1200-per-share/",
};

const awards = {
  text: "We’re thrilled to be named #1 for the Finance category of  @FastCompany’s Most Innovative Companies for 2024! In 2023, we made a big push into payments, helping our customers access faster payments via new rails (RTP & FedNow) and keeping the ecosystem safe at the same time with anti-fraud tools like Signal. ",
  citationLink: "https://x.com/Plaid/status/1770101238379516302",
};

const announcements = {
  text: "Plaid is proud to announce its strategic collaboration with Western Union, a global leader in cross-border and cross-currency payments.",
  citationLink: "https://plaid.com/blog/westernunion-europe-launch",
};

const productUpdates = {
  text: "Introducing Plaid Layer: The future of secure instant financial experiences. Plaid Layer is a new platform for secure, instant experiences that transforms how people use financial services starting with onboarding.",
  citationLink: "https://plaid.com/blog/introducing-plaid-layer",
};

function InfoCard({ text, citationLink = null }) {
  return (
    <Card>
      <Text>{text}</Text>
      <div>
        {citationLink && (
          <Button type="link" href={citationLink}>
            {citationLink}
          </Button>
        )}
      </div>
    </Card>
  );
}

function InfoSection({ sectionTitle, cardInfo = null }) {
  const [cardClicked, setCardClicked] = useState(false);
  return (
    <>
      <Button
        className="info-section-btn"
        type="primary"
        onClick={() => setCardClicked(!cardClicked)}
      >
        {sectionTitle}
      </Button>
      {cardClicked && (
        <InfoCard text={cardInfo.text} citationLink={cardInfo.citationLink} />
      )}
    </>
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
          <InfoSection
            sectionTitle="About"
            cardInfo={aboutPerson}
          ></InfoSection>
          <InfoSection
            sectionTitle="Thoughts"
            cardInfo={thoughts}
          ></InfoSection>
          <InfoSection
            sectionTitle="Events Attended"
            cardInfo={events}
          ></InfoSection>
          <InfoSection
            sectionTitle="Fundraise Announcements"
            cardInfo={fundraise}
          ></InfoSection>
          <InfoSection
            sectionTitle="Awards and Recognition"
            cardInfo={awards}
          ></InfoSection>
          <InfoSection
            sectionTitle="Company Announcements"
            cardInfo={announcements}
          ></InfoSection>
          <InfoSection
            sectionTitle="Product Updates"
            cardInfo={productUpdates}
          ></InfoSection>
        </Flex>
        <Flex id="outreach-container" vertical={true} gap="large">
          <Title level={4}>Sample Outreach Messages</Title>
          <InfoCard text={outreachMessages[0]} />
          <InfoCard text={outreachMessages[1]} />
        </Flex>
      </div>
    </div>
  );
}

export default LeadResult;
