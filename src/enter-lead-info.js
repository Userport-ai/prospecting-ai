import "./enter-lead-info.css";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { Typography, Flex, Form, Input, Button } from "antd";
import { useNavigate } from "react-router-dom";

const { Title } = Typography;

function EnterLeadInfo() {
  const navigate = useNavigate();
  return (
    <div id="enter-lead-info-outer">
      <div id="enter-lead-info-container">
        <div id="form-container">
          <Flex vertical={false} gap="middle">
            <ArrowLeftOutlined onClick={() => navigate("/")} />
            <Title level={3}>Enter Lead information</Title>
          </Flex>
          <Form
            name="enter_lead"
            labelCol={{
              offset: 1,
              span: 3,
            }}
            wrapperCol={{
              offset: 1,
              span: 13,
            }}
            autoComplete="off"
          >
            <Form.Item
              label="LinkedIn URL"
              name="linkedin_url"
              rules={[
                {
                  required: true,
                  message: "Please enter a valid LinkedIn URL!",
                },
              ]}
            >
              <Input />
            </Form.Item>

            <Form.Item
              wrapperCol={{
                offset: 16,
                span: 16,
              }}
            >
              <Button type="primary" htmlType="submit">
                Submit
              </Button>
            </Form.Item>
          </Form>
        </div>
      </div>
    </div>
  );
}

export default EnterLeadInfo;
