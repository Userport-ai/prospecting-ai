import "./all-templates.css";
import { Flex, Typography, Button } from "antd";
import { useNavigate } from "react-router-dom";
import TemplateCard from "./template-card";
import { getTemplateMessages } from "./create-template-message-data";
import { useLoaderData, redirect } from "react-router-dom";

const { Title } = Typography;

export const templateMessagesLoader = (authContext) => {
  return async ({ params }) => {
    const { user } = authContext;
    if (!user) {
      // User is logged out.
      return redirect("/login");
    }
    const templateMessages = getTemplateMessages();
    return { templateMessages };
  };
};

function AllTemplates() {
  const navigate = useNavigate();
  const { templateMessages } = useLoaderData();

  return (
    <div id="all-templates-outer">
      <Flex id="all-templates-outer-container" vertical={true} gap="large">
        <Title level={3}>Template Messages</Title>
        <Flex vertical={false} wrap gap={100}>
          {templateMessages.map((template) => (
            <TemplateCard templateDetails={template} />
          ))}
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
