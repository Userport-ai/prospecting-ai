import "./all-templates.css";
import { Typography, Button, Spin, Modal } from "antd";
import { ExclamationCircleOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import TemplateCard from "./template-card";
import { exampleTemplateResponse } from "./create-template-message-data";
import { useLoaderData, redirect, useNavigation } from "react-router-dom";
import { useContext, useState } from "react";
import { AuthContext } from "./root";

const { Title } = Typography;
const { confirm } = Modal;

export const templateMessagesLoader = (authContext) => {
  return async () => {
    const { user } = authContext;
    if (!user) {
      // User is logged out.
      return redirect("/login");
    }
    const response = await fetch("/api/v1/outreach-email-templates", {
      headers: { Authorization: "Bearer " + user.accessToken },
    });
    const result = await response.json();
    // const result = exampleTemplateResponse;
    if (result.status === "error") {
      throw result;
    }
    return result.outreach_email_templates;
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
      const response = await fetch(
        "api/v1/outreach-email-templates/" + templateId,
        {
          method: "DELETE",
          headers: { Authorization: "Bearer " + user.accessToken },
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
        <h2>No Templates Created</h2>
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
  const navigation = useNavigation();
  const loading_or_submitting = navigation.state !== "idle";
  const outreachEmailTemplates = useLoaderData();
  const [emailTemplates, setEmailTemplates] = useState(outreachEmailTemplates);
  const { user } = useContext(AuthContext);

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

  return (
    <>
      <div id="all-templates-outer">
        <div id="outer-with-spinner">
          <Spin spinning={loading_or_submitting} />;
          <div id="all-templates-outer-container">
            <div id="templates-title-container">
              <Title level={3}>All Email Templates</Title>
              <Button
                id="create-template-btn"
                type="primary"
                htmlType="submit"
                onClick={() => navigate("/create-template")}
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
