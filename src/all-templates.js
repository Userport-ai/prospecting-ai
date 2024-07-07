import "./all-templates.css";
import { Flex, Typography, Button } from "antd";
import { useNavigate } from "react-router-dom";
import TemplateCard from "./template-card";
import { exampleTemplate } from "./create-template-message-data";

const { Title } = Typography;

function AllTemplates() {
  const navigate = useNavigate();
  return (
    <div id="all-templates-outer">
      <Flex id="all-templates-outer-container" vertical={true} gap="large">
        <Title level={3}>Template Messages</Title>
        <Flex vertical={false} wrap gap={100}>
          <TemplateCard templateDetails={exampleTemplate}></TemplateCard>
          <TemplateCard templateDetails={exampleTemplate}></TemplateCard>
        </Flex>

        <Flex vertical={false} justify="flex-start">
          <Button
            type="primary"
            htmlType="submit"
            // TODO: change to use action and send data to server
            onClick={() => navigate("/create-template")}
          >
            Create new template
          </Button>
        </Flex>
      </Flex>
    </div>
  );
}

export default AllTemplates;
