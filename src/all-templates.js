import "./all-templates.css";
import { Typography, Button } from "antd";
import { useNavigate } from "react-router-dom";
import TemplateCard from "./template-card";
import { exampleTemplateResponse } from "./create-template-message-data";
import { useLoaderData, redirect } from "react-router-dom";

const { Title } = Typography;

export const templateMessagesLoader = (authContext) => {
  return async ({ params }) => {
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

function TemplatesView({ templateMessages }) {
  if (templateMessages.length === 0) {
    return (
      <div id="no-templates-created-container">
        <h2>No Templates Created</h2>
      </div>
    );
  }
  return templateMessages.map((template) => (
    <TemplateCard key={template.id} templateDetails={template} />
  ));
}

function AllTemplates() {
  const navigate = useNavigate();
  const outreachEmailTemplates = useLoaderData();

  return (
    <div id="all-templates-outer">
      <div id="all-templates-outer-container">
        <div id="templates-title-container">
          <Title level={3}>All Email Templates</Title>
          <Button
            type="primary"
            htmlType="submit"
            onClick={() => navigate("/create-template")}
          >
            Create
          </Button>
        </div>
        <div id="template-cards-container">
          <TemplatesView templateMessages={outreachEmailTemplates} />
        </div>
      </div>
    </div>
  );
}

export default AllTemplates;
