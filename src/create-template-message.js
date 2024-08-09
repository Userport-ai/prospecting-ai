import "./create-template-message.css";
import { Typography, Input, Button, Spin } from "antd";
import BackArrow from "./back-arrow";
import { useState } from "react";
import { Form as RouterForm, useNavigation, redirect } from "react-router-dom";

const { Title, Text } = Typography;
const { TextArea } = Input;

export const createTemplateAction = (authContext) => {
  return async ({ request }) => {
    const { user } = authContext;
    if (!user) {
      // User is logged out.
      return null;
    }
    const formData = await request.formData();
    const apiRequest = Object.fromEntries(formData);
    if (apiRequest["persona_role_titles"].length === 0) {
      throw { message: "Role Titles Cannot be empty", status_code: 400 };
    }
    if (apiRequest["message"].length === 0) {
      throw { message: "Template message Cannot be empty", status_code: 400 };
    }

    const response = await fetch("/api/v1/outreach-email-templates", {
      method: "POST",
      body: JSON.stringify(apiRequest),
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + user.accessToken,
      },
    });
    const result = await response.json();
    if (result.status === "error") {
      console.log("Got error when creating outreach email template: ", result);
      throw result;
    }

    // Successful creation, go back to all templates page.
    return redirect("/templates");
  };
};

function DisplaySpinState({ loading_or_submitting }) {
  return (
    <div id="spinner-container">
      <Spin spinning={loading_or_submitting} />
    </div>
  );
}

function CreateTemplateMessage() {
  const [currMessage, setCurrMessage] = useState("");
  const navigation = useNavigation();
  const loading_or_submitting = navigation.state !== "idle";

  return (
    <div id="create-template-message-outer">
      <div id="create-template-message-area">
        <DisplaySpinState loading_or_submitting={loading_or_submitting} />
        <div id="page-title">
          <BackArrow />
        </div>
        <div id="create-template-message-container">
          <div id="form-container">
            <Title level={3}>Create Email Template</Title>
            <RouterForm method="post">
              <div id="role-titles-container">
                <label htmlFor="persona-role-titles-input">
                  Persona Role Titles
                </label>
                <Text className="label-helper-text">
                  You can enter multiple roles by separating them with commas.
                  Ex: VP of Sales, Director of Sales, CEO.
                </Text>
                <Input
                  id="persona-role-titles-input"
                  name="persona_role_titles"
                />
              </div>

              <div id="description-container">
                <label htmlFor="description-input">
                  Description (Optional)
                </label>
                <Text className="label-helper-text">
                  Free form text describing the persona's skillset or background
                  or any other specific detail. Ex: Experienced in Outbound
                  Sales.
                </Text>
                <Input id="description-input" name="description" />
              </div>

              <div id="message-container">
                <label htmlFor="message-textarea">Message</label>
                <Text className="label-helper-text">
                  The template message that shines light on the problem and
                  provides the value proposition of your product.
                </Text>
                <TextArea
                  id="message-textarea"
                  name="message"
                  value={currMessage}
                  onChange={(e) => setCurrMessage(e.target.value)}
                  autoSize={{ minRows: 10, maxRows: 100 }}
                />
              </div>

              <div id="btn-container">
                <Button type="primary" htmlType="submit">
                  Create
                </Button>
              </div>
            </RouterForm>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CreateTemplateMessage;
