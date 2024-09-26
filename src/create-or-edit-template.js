import "./create-or-edit-template.css";
import { Typography, Input, Button, Skeleton, Modal } from "antd";
import BackArrow from "./back-arrow";
import { useContext, useState } from "react";
import { redirect, useLoaderData, useNavigate } from "react-router-dom";
import {
  stateAfterFirstTemplateCreation,
  updateUserStateOnServer,
  userHasNotCreatedTemplate,
} from "./helper-functions";
import { usePostHog } from "posthog-js/react";
import { AuthContext } from "./root";

const { Title, Text } = Typography;
const { TextArea } = Input;

// Loader for template. If it is creation flow, returns null, else returns existing template details from backend.
export const createOrEditTemplateLoader = (authContext) => {
  return async ({ request, params }) => {
    const { user } = authContext;
    if (!user) {
      // User is logged out.
      return redirect("/login");
    }
    // Loader response object.
    var loaderResponse = { userState: null, outreachEmailTemplate: null };

    if (request.url) {
      // User state present in the URL.
      const url = new URL(request.url);
      loaderResponse.userState = url.searchParams.get("state");
    }

    if (params.id === undefined) {
      // Create template flow, return response immediately.
      return loaderResponse;
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
    loaderResponse.outreachEmailTemplate = result.outreach_email_template;
    return loaderResponse;
  };
};

// Template message used to reach out to prospect.
function OutreachMessage({ outreachMessages, index, onChange }) {
  var labelText = "";
  var helperText = "";
  var message = outreachMessages[index];
  const textAreaName = `message-${index.toString()}`;
  if (index === 0) {
    // First email.
    labelText = "First Email";
    helperText =
      "Write a message that shines light on the prospect's problem as well as the value proposition of your product or service.";
  } else {
    // Follow up email.
    labelText = `Follow Up - ${(index + 1).toString()}`;
    helperText =
      "Write a follow up message to remind your prospect about your previous outreach.";
  }

  return (
    <div className="form-item-container">
      <label htmlFor="message-textarea">{labelText}</label>
      <Text className="label-helper-text">{helperText}</Text>
      <TextArea
        id="message-textarea"
        name={textAreaName}
        value={message}
        onChange={(e) => onChange(e.target.value, index)}
        autoSize={{ minRows: 10, maxRows: 100 }}
      />
    </div>
  );
}

// Main component to create or edit template.
function CreateOrEditTemplate() {
  const loaderResponse = useLoaderData();
  const { user } = useContext(AuthContext);
  const firstTemplateCreation = userHasNotCreatedTemplate(
    loaderResponse.userState
  );
  const existingOutreachTemplate = loaderResponse.outreachEmailTemplate;
  const [templateName, setTemplateName] = useState(
    existingOutreachTemplate ? existingOutreachTemplate.name : ""
  );
  const [templateRoleTitles, setTemplateRoleTitles] = useState(
    existingOutreachTemplate
      ? existingOutreachTemplate.persona_role_titles.join(",")
      : ""
  );
  const [templateDescription, setTemplateDescription] = useState(
    existingOutreachTemplate ? existingOutreachTemplate.description : ""
  );
  const [outreachMessages, setOutreachMessages] = useState(
    existingOutreachTemplate ? existingOutreachTemplate.messages : [""]
  );
  const pageTitle = existingOutreachTemplate
    ? "Edit Email Template"
    : "Create Email Template";
  const actionButtonText = existingOutreachTemplate ? "Save" : "Create";

  const [formSubmitting, setFormSubmitting] = useState(false);
  const posthog = usePostHog();
  const navigate = useNavigate();

  if (formSubmitting) {
    return (
      <Skeleton
        active
        paragraph={{
          rows: 15,
        }}
      />
    );
  }

  // Handle changes to outreach message made by the user.
  function handleOutreachMessageUpdate(newMessage, index) {
    if (index < 0 || index >= outreachMessages.length) {
      // Invalid index value.
      const error_obj = {
        message: "Invalid index value: " + index.toString(),
        status_code: 400,
      };
      throw error_obj;
    }

    const newOutreachMessages = outreachMessages.map((message, i) => {
      if (i === index) {
        return newMessage;
      }
      return message;
    });
    setOutreachMessages(newOutreachMessages);
  }

  // Handle request to submit template to the server.
  async function handleCreateOrEditTemplateRequest() {
    var error_message = "";
    if (!templateName) {
      error_message = "Template Name cannot be empty";
    } else if (!templateRoleTitles) {
      error_message = "Role Titles cannot be empty";
    } else {
      // Template description is optional, so not validating its value here.
      for (let i in outreachMessages) {
        if (!outreachMessages[i]) {
          error_message = "Email or Follow up messages cannot be empty";
          break;
        }
      }
    }
    if (error_message) {
      Modal.error({
        title: "Missing Required fields!",
        content: error_message,
      });
      return;
    }

    setFormSubmitting(true);
    const templateId = existingOutreachTemplate
      ? existingOutreachTemplate.id
      : null;

    const idToken = await user.getIdToken();
    var apiEndpoint = "/api/v1/outreach-email-templates";
    var apiMethod = "POST";
    if (templateId !== null) {
      // Edit template endpoint.
      apiEndpoint = apiEndpoint + "/" + templateId;
      apiMethod = "PUT";
    }

    // Send request to server to create or edit template.
    const response = await fetch(apiEndpoint, {
      method: apiMethod,
      body: JSON.stringify({
        name: templateName,
        persona_role_titles: templateRoleTitles,
        description: templateDescription,
        message: outreachMessages[0],
      }),
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + idToken,
      },
    });
    const result = await response.json();
    if (result.status === "error") {
      setFormSubmitting(false);
      Modal.error({
        title: `Error: ${result.status_code.toString()}`,
        content: result.message,
      });
    }

    // Update user state if first template creation.
    if (firstTemplateCreation) {
      await updateUserStateOnServer(stateAfterFirstTemplateCreation(), idToken);
    }

    // Send event.
    if (templateId === null) {
      posthog.capture("create_template_form_submitted");
    } else {
      posthog.capture("edit_template_form_submitted", {
        template_id: templateId,
      });
    }

    // Successful creation or edit, go back to all templates page.
    return navigate("/templates");
  }

  return (
    <div id="create-or-edit-template-outer">
      <div id="create-or-edit-template-area">
        <div id="page-title">
          <BackArrow />
        </div>
        <div id="create-or-edit-template-container">
          <div id="form-container">
            <Title level={3}>{pageTitle}</Title>
            <div id="form-item-list">
              <div className="form-item-container">
                <label htmlFor="name-input">Template Name</label>
                <Text className="label-helper-text">
                  Enter a name for the template that you can use to reference
                  it. You can any enter name, just ensure it is unique among all
                  your templates.
                </Text>
                <Input
                  id="name-input"
                  name="name"
                  defaultValue={templateName}
                  onChange={(e) => setTemplateName(e.target.value)}
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
                  defaultValue={templateRoleTitles}
                  onChange={(e) => setTemplateRoleTitles(e.target.value)}
                />
              </div>

              <div className="form-item-container">
                <label htmlFor="description-input">
                  Description (Optional)
                </label>
                <Text className="label-helper-text">
                  Free form text describing the persona's skillset or background
                  or any other specific detail. Ex: Experienced in Outbound
                  Sales.
                </Text>
                <Input
                  id="description-input"
                  name="description"
                  defaultValue={templateDescription}
                  onChange={(e) => setTemplateDescription(e.target.value)}
                />
              </div>

              {/* Add email messages here. */}
              {outreachMessages.map((_, index) => {
                return (
                  <OutreachMessage
                    key={index}
                    outreachMessages={outreachMessages}
                    index={index}
                    onChange={handleOutreachMessageUpdate}
                  />
                );
              })}

              {/* Whether this is the first template the user is creating. */}
              <Input
                hidden={true}
                name="first_template_creation"
                defaultValue={firstTemplateCreation}
              />

              <div id="btn-container">
                <Button
                  type="primary"
                  htmlType="submit"
                  onClick={handleCreateOrEditTemplateRequest}
                >
                  {actionButtonText}
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CreateOrEditTemplate;
