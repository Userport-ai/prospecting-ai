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

  function toCommaSeparatedString(persona_role_titles) {
    return persona_role_titles.join(", ");
  }

  function handleDelete() {
    return onDeleteTemplate(templateDetails.id);
  }

  return (
    <Card key={templateDetails.id} className="template-card">
      <div className="contents-and-btn-container">
        <div className="card-contents-container">
          <Flex vertical={false} gap="small">
            <Text className="card-key">Name:</Text>
            <Text className="card-key-value-text">{templateDetails.name}</Text>
          </Flex>

          <Flex vertical={false} gap="small">
            <Text className="card-key">Role Titles:</Text>
            <Text className="card-key-value-text">
              {toCommaSeparatedString(templateDetails.persona_role_titles)}
            </Text>
          </Flex>
          <Flex vertical={false} gap="small">
            <Text className="card-key">Description (Optional):</Text>
            <Text className="card-key-value-text">
              {templateDetails.description}
            </Text>
          </Flex>
          <Flex vertical={true} gap="small">
            <Text className="card-key">Message:</Text>
            <Text className="card-key-value-text">
              {addLineBreaks(templateDetails.message)}
            </Text>
          </Flex>

          <div className="dates-container">
            <div className="created-date-container">
              <Text className="date-key">Created On:</Text>
              <Text className="date-key-value-text">
                {templateDetails.creation_date_readable_str}
              </Text>
            </div>
            <div className="updated-date-container">
              <Text className="date-key">Last Edited On:</Text>
              <Text className="date-key-value-text">
                {templateDetails.last_updated_date_readable_str}
              </Text>
            </div>
          </div>
        </div>
        <Button
          className="delete-btn"
          onClick={handleDelete}
          icon={<DeleteOutlined style={{ color: "#65558f" }} />}
        ></Button>
      </div>
    </Card>
  );
}

export default TemplateCard;
