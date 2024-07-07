import "./create-template-message.css";
import { exampleTemplate } from "./create-template-message-data";
import { Flex, Typography, Form, Input, Button } from "antd";
import BackArrow from "./back-arrow";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

const { Title } = Typography;
const { TextArea } = Input;

function CreateTemplateMessage() {
  const navigate = useNavigate();
  const [currMessage, setCurrMessage] = useState(exampleTemplate.message);
  return (
    <div id="create-template-message-outer">
      <div id="create-template-message-area">
        <Flex
          id="create-template-message-container"
          vertical={true}
          gap="middle"
        >
          <Flex vertical={false} gap="middle">
            <BackArrow />
            <Title level={3}>Create Template Message</Title>
          </Flex>
          <Form
            layout="vertical"
            labelCol={{ span: 10 }}
            wrapperCol={{ span: 20 }}
          >
            <Form.Item
              label="Role Titles"
              name="role-titles"
              rules={[
                { required: true, message: "Please enter valid role titles!" },
              ]}
            >
              <Input defaultValue={exampleTemplate.roleTitles} />
            </Form.Item>

            <Form.Item
              label="Additional Keywords (optional)"
              name="additional-keywords"
              rules={[{ required: false }]}
            >
              <Input defaultValue={exampleTemplate.additionalKeywords} />
            </Form.Item>

            <Form.Item
              label="Message"
              name="message"
              rules={[{ required: true, message: "Message cannot be empty!" }]}
            >
              <TextArea
                defaultValue={currMessage}
                value={currMessage}
                onChange={(e) => setCurrMessage(e.target.value)}
                autoSize={{ minRows: 5, maxRows: 100 }}
              />
            </Form.Item>
          </Form>
          <Flex id="btn-container" vertical={false} justify="flex-end">
            <Button
              type="primary"
              htmlType="submit"
              // TODO: change to use action and send data to server
              onClick={() => navigate("/templates")}
            >
              Create
            </Button>
          </Flex>
        </Flex>
      </div>
    </div>
  );
}

export default CreateTemplateMessage;
