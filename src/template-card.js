import "./template-card.css";
import { Card, Flex, Typography } from "antd";

const { Text } = Typography;

function TemplateCard({ templateDetails }) {
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

  return (
    <Card className="template-card">
      <Flex vertical={true} gap="middle">
        <Flex vertical={false} gap="small">
          <Text className="card-key">Role Titles:</Text>
          <Text>{templateDetails.roleTitles}</Text>
        </Flex>
        <Flex vertical={false} gap="small">
          <Text className="card-key">Additional Keywords:</Text>
          <Text>{templateDetails.additionalKeywords}</Text>
        </Flex>
        <Flex vertical={true} gap="small">
          <Text className="card-key">Message:</Text>
          <Text>{addLineBreaks(templateDetails.message)}</Text>
        </Flex>
      </Flex>
    </Card>
  );
}

export default TemplateCard;
