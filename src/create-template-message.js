import "./create-template-message.css";
import { Typography, Input, Button, Spin } from "antd";
import BackArrow from "./back-arrow";
import { useState } from "react";
import {
  Form as RouterForm,
  useNavigation,
  redirect,
  useLoaderData,
} from "react-router-dom";

const { Title, Text } = Typography;
const { TextArea } = Input;

// Loader for template. If it is creation flow, returns null, else returns existing template details from backend.
export const createOrEditTemplateLoader = (authContext) => {
  return async ({ params }) => {
    const { user } = authContext;
    if (!user) {
      // User is logged out.
      return redirect("/login");
    }
    if (params.id === undefined) {
      // Create template flow, load nothing.
      return null;
    }

    // Fetch template to edit from backend.
    const templateId = params.id;
    const idToken = await user.getIdToken();
    const response = await fetch(
      "/api/v1/outreach-email-templates/" + templateId,
      {
        headers: { Authorization: "Bearer " + idToken },
      }
    );
    const result = await response.json();
    if (result.status === "error") {
      throw result;
    }
    return result.outreach_email_template;
  };
};

// Creates new template after user fills out new template form.
export const createTemplateAction = (authContext) => {
  return async ({ request }) => {
    const { user } = authContext;
    if (!user) {
      // User is logged out.
      return null;
    }
    const formData = await request.formData();
    const apiRequest = Object.fromEntries(formData);
    if (apiRequest["name"].length === 0) {
      const error_obj = {
        message: "Template Name Cannot be empty",
        status_code: 400,
      };
      throw error_obj;
    }
    if (apiRequest["persona_role_titles"].length === 0) {
      const error_obj = {
        message: "Role Titles Cannot be empty",
        status_code: 400,
      };
      throw error_obj;
    }
    if (apiRequest["message"].length === 0) {
      const error_obj = {
        message: "Template message Cannot be empty",
        status_code: 400,
      };
      throw error_obj;
    }

    const idToken = await user.getIdToken();
    const response = await fetch("/api/v1/outreach-email-templates", {
      method: "POST",
      body: JSON.stringify(apiRequest),
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + idToken,
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

function CreateOrEditTemplateMessage() {
  const existingOutreachTemplate = useLoaderData();
  const [currMessage, setCurrMessage] = useState(
    existingOutreachTemplate ? existingOutreachTemplate.message : ""
  );
  const navigation = useNavigation();
  const loading_or_submitting = navigation.state !== "idle";
  const pageTitle = existingOutreachTemplate
    ? "Edit Email Template"
    : "Create Email Template";
  const actionButtonText = existingOutreachTemplate ? "Save" : "Create";

  return (
    <div id="create-template-message-outer">
      <div id="create-template-message-area">
        <DisplaySpinState loading_or_submitting={loading_or_submitting} />
        <div id="page-title">
          <BackArrow />
        </div>
        <div id="create-template-message-container">
          <div id="form-container">
            <Title level={3}>{pageTitle}</Title>
            <RouterForm method="post">
              <div id="form-item-list">
                <div className="form-item-container">
                  <label htmlFor="name-input">Template Name</label>
                  <Text className="label-helper-text">
                    Enter a name for the template that you can use to reference
                    it. You can any enter name, just ensure it is unique among
                    all your templates.
                  </Text>
                  <Input
                    id="name-input"
                    name="name"
                    defaultValue={
                      existingOutreachTemplate
                        ? existingOutreachTemplate.name
                        : ""
                    }
                  />
                </div>

                <div className="form-item-container">
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
                    defaultValue={
                      existingOutreachTemplate
                        ? existingOutreachTemplate.persona_role_titles
                        : ""
                    }
                  />
                </div>

                <div className="form-item-container">
                  <label htmlFor="description-input">
                    Description (Optional)
                  </label>
                  <Text className="label-helper-text">
                    Free form text describing the persona's skillset or
                    background or any other specific detail. Ex: Experienced in
                    Outbound Sales.
                  </Text>
                  <Input
                    id="description-input"
                    name="description"
                    defaultValue={
                      existingOutreachTemplate
                        ? existingOutreachTemplate.description
                        : ""
                    }
                  />
                </div>

                <div className="form-item-container">
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
                    {actionButtonText}
                  </Button>
                </div>
              </div>
            </RouterForm>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CreateOrEditTemplateMessage;
