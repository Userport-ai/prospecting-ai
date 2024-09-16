import "./enter-lead-info.css";
import { Typography, Flex, Form, Input, Button, Skeleton, Modal } from "antd";
import BackArrow from "./back-arrow";
import {
  Form as RouterForm,
  useRouteError,
  useNavigation,
  redirect,
  useLoaderData,
} from "react-router-dom";
import { useState } from "react";
import {
  stateAfterFirstLeadCreation,
  updateUserStateOnServer,
  userHasNotCreatedLead,
} from "./helper-functions";

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
    const first_lead_addition = inputValueMap["first_lead_addition"];

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
      // Show rate limit error to the user in a Modal.
      var title = "Error adding lead!";
      var description = result.message;
      if (result.status_code === 429) {
        if (result.message.includes("minute")) {
          title = "Error! Too many leads added at once!";
          description =
            "Please wait for some of the existing lead reports to finish and then retry.";
        } else if (result.message.includes("day")) {
          title = "Error! Limit exhausted!";
          description =
            "Exceeded lead creation limit for the day, please try again in 24 hours.";
        }
        Modal.error({
          title: title,
          content: description,
        });
        return null;
      }
      // Any other error, throw it so it can be caught by component.
      throw result;
    }

    // Update user state if first lead addition.
    if (first_lead_addition) {
      await updateUserStateOnServer(stateAfterFirstLeadCreation(), idToken);
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

export function enterLeadInfoLoader({ request }) {
  if (!request.url) {
    // User state not passed in the URL.
    return null;
  }
  const url = new URL(request.url);
  return url.searchParams.get("state");
}

// Main component.
function EnterLeadInfo() {
  const [inputURL, setInputURL] = useState("");
  const error = useRouteError();
  const component_is_loading = useNavigation().state !== "idle";
  const firstLeadAddition = userHasNotCreatedLead(useLoaderData());

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
                value={inputURL}
                onChange={(e) => setInputURL(e.target.value)}
                name="linkedin_url"
              />
            </Form.Item>

            {/* Whether this is the first lead the user is adding. */}
            <Input
              hidden={true}
              name="first_lead_addition"
              defaultValue={firstLeadAddition}
            />

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
