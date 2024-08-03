import "./enter-lead-info.css";
import { Typography, Flex, Form, Input, Button } from "antd";
import BackArrow from "./back-arrow";
import { Form as RouterForm, useRouteError } from "react-router-dom";
import { useState } from "react";

const { Title } = Typography;

export async function enterLeadAction({ request, params }) {
  const formData = await request.formData();
  const inputValueMap = Object.fromEntries(formData);
  const linkedin_url = inputValueMap["linkedin_url"];

  const response = await fetch("/api/v1/lead_report", {
    method: "POST",
    body: JSON.stringify({ linkedin_url: linkedin_url }),
    headers: {
      "Content-Type": "application/json",
    },
  });
  const result = await response.json();
  if (result.status === "error") {
    // Throw error so it can be caught by component.
    throw result;
  }

  // TODO: Handle success case.
  return null;
}

function DisplayError({ error }) {
  if (error) {
    return <p id="error-message">{error.message}</p>;
  }
  return null;
}

function EnterLeadInfo() {
  const [inputURL, setInputURL] = useState("");

  const error = useRouteError();

  return (
    <div id="enter-lead-info-outer">
      <div id="enter-lead-info-container">
        <div id="form-container">
          <Flex vertical={false} gap="middle">
            <BackArrow />
            <Title level={3}>Enter Lead information</Title>
          </Flex>
          <DisplayError error={error} />
          <RouterForm id="enter-lead-form" method="post">
            <Form.Item label="LinkedIn URL">
              <Input
                defaultValue="https://www.linkedin.com/in/zperret/"
                value={inputURL}
                onChange={(e) => setInputURL(e.target.value)}
                name="linkedin_url"
              />
            </Form.Item>
            <Flex vertical={false} justify="flex-end">
              <Button type="primary" htmlType="submit">
                Submit
              </Button>
            </Flex>
          </RouterForm>
        </div>
      </div>
    </div>
  );
}

export default EnterLeadInfo;
