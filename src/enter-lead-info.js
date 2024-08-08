import "./enter-lead-info.css";
import { Typography, Flex, Form, Input, Button, Spin } from "antd";
import BackArrow from "./back-arrow";
import {
  Form as RouterForm,
  useRouteError,
  useNavigation,
} from "react-router-dom";
import { useState } from "react";

const { Title } = Typography;

export const enterLeadAction = (authContext) => {
  return async ({ request, params }) => {
    const { user } = authContext;
    if (!user) {
      // User is logged out.
      return null;
    }

    const formData = await request.formData();
    const inputValueMap = Object.fromEntries(formData);
    const linkedin_url = inputValueMap["linkedin_url"];

    const response = await fetch("/api/v1/lead-research-reports", {
      method: "POST",
      body: JSON.stringify({ linkedin_url: linkedin_url }),
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + user.accessToken,
      },
    });
    const result = await response.json();
    if (result.status === "error") {
      // Throw error so it can be caught by component.
      console.log("Got error when creating lead research report: ", result);
      throw result;
    }

    // TODO: Handle state where it research report is still in progress.
  };
};

function DisplayError({ error }) {
  if (error) {
    return <p id="error-message">{error.message}</p>;
  }
  return null;
}

function DisplaySpinState({ loading_or_submitting }) {
  return (
    <Flex id="spinner-container" vertical={false} justify="center">
      <Spin spinning={loading_or_submitting} />
    </Flex>
  );
}

function EnterLeadInfo() {
  const [inputURL, setInputURL] = useState("");

  const error = useRouteError();

  const navigation = useNavigation();

  const loading_or_submitting = navigation.state !== "idle";

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
              <Button
                type="primary"
                htmlType="submit"
                disabled={loading_or_submitting}
              >
                Submit
              </Button>
            </Flex>
          </RouterForm>
          <DisplaySpinState loading_or_submitting={loading_or_submitting} />
        </div>
      </div>
    </div>
  );
}

export default EnterLeadInfo;
