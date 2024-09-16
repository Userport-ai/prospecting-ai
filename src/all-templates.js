import "./all-templates.css";
import { Button, Skeleton, Modal, Typography } from "antd";
import { ExclamationCircleOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import TemplateCard from "./template-card";
import { useLoaderData, redirect, useNavigation } from "react-router-dom";
import { useContext, useState } from "react";
import { AuthContext } from "./root";
import OnboardingProgressBar from "./onboarding-progress-bar";
import {
  isUserOnboarding,
  userHasNotCreatedTemplate,
} from "./helper-functions";
import { usePostHog } from "posthog-js/react";

const { confirm } = Modal;
const { Text } = Typography;

// Loader for templates created by a user.
export const templateMessagesLoader = (authContext) => {
  return async () => {
    const { user } = authContext;
    if (!user) {
      // User is logged out.
      return redirect("/login");
    }
    const idToken = await user.getIdToken();
    const response = await fetch("/api/v1/outreach-email-templates", {
      headers: { Authorization: "Bearer " + idToken },
    });
    const result = await response.json();
    if (result.status === "error") {
      throw result;
    }
    return result;
  };
};

const showDeletionConfirmModal = (
  user,
  templateId,
  handleErrorInModal,
  handleTemplateDeletionSuccessInModal
) => {
  confirm({
    title: "Are you sure you want to delete this Template?",
    icon: <ExclamationCircleOutlined />,
    content: "This event cannot be undone.",
    async onOk() {
      const idToken = await user.getIdToken();
      const response = await fetch(
        "api/v1/outreach-email-templates/" + templateId,
        {
          method: "DELETE",
          headers: { Authorization: "Bearer " + idToken },
        }
      );
      const result = await response.json();
      if (result.status === "error") {
        return handleErrorInModal(result);
      }
      return handleTemplateDeletionSuccessInModal(templateId);
    },
    onCancel() {
      // Do nothing.
    },
  });
};

const showDeletionFailedModal = (error) => {
  Modal.error({
    title: "Failed to Delete Template",
    content: error.status_code + ": " + error.message,
  });
};

function TemplatesView({ templateMessages, onDeleteTemplate }) {
  if (templateMessages.length === 0) {
    return (
      <div id="no-templates-created-container">
        <h2>No Templates Created Yet</h2>
        <Text className="templates-description">
          Email templates shine light on the pain points of the prospect and
          explain the value proposition of their solution.
        </Text>
        <Text className="templates-description">
          Use the Create button above to create templates for each type of
          persona you plan to target.
        </Text>
      </div>
    );
  }
  return templateMessages.map((template) => (
    <TemplateCard
      key={template.id}
      templateDetails={template}
      onDeleteTemplate={onDeleteTemplate}
    />
  ));
}

function AllTemplates() {
  const navigate = useNavigate();
  const component_is_loading = useNavigation().state !== "idle";
  const loaderResult = useLoaderData();
  const [emailTemplates, setEmailTemplates] = useState(
    loaderResult.outreach_email_templates
  );
  // User object stored in server's database.
  const userFromServer = loaderResult.user;
  // This is Firebase user object.
  const { user } = useContext(AuthContext);
  const posthog = usePostHog();

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

  // Handle template deletion success in Modal.
  function handleTemplateDeletionSuccessInModal(templateId) {
    // Update templates list.
    setEmailTemplates(
      emailTemplates.filter((template) => template.id !== templateId)
    );
  }

  // Handle error thrown in confirmation modal.
  function handleErrorInModal(error) {
    showDeletionFailedModal(error);
  }

  // Handle for Template deletion event.
  function onDeleteTemplate(templateId) {
    showDeletionConfirmModal(
      user,
      templateId,
      handleErrorInModal,
      handleTemplateDeletionSuccessInModal
    );
  }

  // Handler for when user clicks Create new template button.
  function handleCreateNewTemplate() {
    var nextPage = "/templates/create";
    if (userHasNotCreatedTemplate(userFromServer.state)) {
      // Pass this information about the user in the URL path.
      const urlParams = new URLSearchParams({
        state: userFromServer.state,
      }).toString();
      nextPage += `?${urlParams}`;
    }

    // Send event.
    posthog.capture("create_template_btn_clicked");
    return navigate(nextPage);
  }

  return (
    <>
      {isUserOnboarding(userFromServer) && (
        <OnboardingProgressBar
          userFromServer={userFromServer}
        ></OnboardingProgressBar>
      )}
      <div id="all-templates-outer">
        <div id="outer-with-spinner">
          <div id="all-templates-outer-container">
            <div id="templates-title-container">
              <h1>All Email Templates</h1>
              <Button
                id="create-template-btn"
                type="primary"
                htmlType="submit"
                onClick={handleCreateNewTemplate}
              >
                Create
              </Button>
            </div>
            <div id="template-cards-container">
              <TemplatesView
                templateMessages={emailTemplates}
                onDeleteTemplate={onDeleteTemplate}
              />
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

export default AllTemplates;
