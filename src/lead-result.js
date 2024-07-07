import "./lead-result.css";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { Flex, Typography, Button, Card } from "antd";
import { useNavigate } from "react-router-dom";
import { useState } from "react";
import { personInfoList, outreachMessages } from "./lead-result-data";

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

function InfoCard({ cardInfo }) {
  return (
    <Card>
      <Text className="card-text">{cardInfo.text}</Text>
      <div>
        <Button
          className="card-citation-link"
          type="link"
          href={cardInfo.citationLink}
        >
          {cardInfo.citationLink}
        </Button>
      </div>
      <Text className="card-date">{cardInfo.date}</Text>
    </Card>
  );
}

function InfoSection({ cardInfo }) {
  const [cardClicked, setCardClicked] = useState(false);
  return (
    <>
      <Button
        className="info-section-btn"
        type="primary"
        onClick={() => setCardClicked(!cardClicked)}
      >
        {cardInfo.title}
      </Button>
      {cardClicked && <InfoCard cardInfo={cardInfo} />}
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
          {personInfoList.map((info) => (
            <InfoSection cardInfo={info} />
          ))}
        </Flex>
        <Flex id="outreach-container" vertical={true} gap="large">
          <Title level={4}>Sample Outreach Messages</Title>
          <OutreachCard text={outreachMessages[0]} />
          <OutreachCard text={outreachMessages[1]} />
        </Flex>
      </div>
    </div>
  );
}

export default LeadResult;
