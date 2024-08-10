import "./template-card.css";
import { Card, Flex, Typography, Button } from "antd";
import { DeleteOutlined } from "@ant-design/icons";

const { Text } = Typography;

function TemplateCard({ templateDetails, onDeleteTemplate }) {
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

  function handleDelete() {
    return onDeleteTemplate(templateDetails.id);
  }

  return (
    <Card key={templateDetails.id} className="template-card">
      <Flex vertical={true} gap="middle">
        <div className="template-role-titles-and-buttons">
          <Flex vertical={false} gap="small">
            <Text className="card-key">Role Titles:</Text>
            <Text>{templateDetails.persona_role_titles}</Text>
          </Flex>
          <Button
            className="delete-btn"
            onClick={handleDelete}
            icon={<DeleteOutlined style={{ color: "#65558f" }} />}
          ></Button>
        </div>

        <Flex vertical={false} gap="small">
          <Text className="card-key">Description (Optional):</Text>
          <Text>{templateDetails.description}</Text>
        </Flex>
        <Flex vertical={true} gap="small">
          <Text className="card-key">Message:</Text>
          <Text>{addLineBreaks(templateDetails.message)}</Text>
        </Flex>
        <Flex vertical={false} gap="small">
          <Text className="card-key">Created:</Text>
          <Text>{templateDetails.creation_date_readable_str}</Text>
        </Flex>
        <Flex vertical={false} gap="small">
          <Text className="card-key">Last Edited:</Text>
          <Text>{templateDetails.last_updated_date_readable_str}</Text>
        </Flex>
      </Flex>
    </Card>
  );
}

export default TemplateCard;
