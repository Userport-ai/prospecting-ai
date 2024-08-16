import "./enter-lead-info.css";
import { Typography, Flex, Form, Input, Button, Skeleton } from "antd";
import BackArrow from "./back-arrow";
import {
  Form as RouterForm,
  useRouteError,
  useNavigation,
  redirect,
} from "react-router-dom";
import { useState } from "react";

const { Title } = Typography;

// Submits lead information to backend.
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

    // Create lead in the backend.
    const idToken = await user.getIdToken();
    const response = await fetch("/api/v1/lead-research-reports", {
      method: "POST",
      body: JSON.stringify({ linkedin_url: linkedin_url }),
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + idToken,
      },
    });
    const result = await response.json();
    if (result.status === "error") {
      // Throw error so it can be caught by component.
      console.log("Got error when creating lead research report: ", result);
      throw result;
    }

    // Redirect to success page with instructions for the user.
    const urlParams = new URLSearchParams({ url: linkedin_url }).toString();
    return redirect("/leads/create/success?" + urlParams);
  };
};

function DisplayError({ error }) {
  if (error) {
    return <p id="error-message">{error.message}</p>;
  }
  return null;
}

function EnterLeadInfo() {
  const [inputURL, setInputURL] = useState("");
  const error = useRouteError();
  const component_is_loading = useNavigation().state !== "idle";

  if (component_is_loading) {
    return (
      <Skeleton
        active
        paragraph={{
          rows: 15,
        }}
      />
    );
  }

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
                disabled={component_is_loading}
              >
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
