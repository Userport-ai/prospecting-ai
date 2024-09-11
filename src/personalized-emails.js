import "./personalized-emails.css";
import { addLineBreaks } from "./helper-functions";
import { Card, Typography, Button, Select } from "antd";
import { EditOutlined } from "@ant-design/icons";
import { useContext, useState } from "react";
import { AuthContext } from "./root";

const { Text, Link } = Typography;

// Edit mode of template.
function TemplateEditMode({
  lead_research_report_id,
  emailId,
  allTemplates,
  onCancel,
  onEditSuccess,
}) {
  // Logged in user.
  const { user } = useContext(AuthContext);
  const [selectedTemplateId, setSelectedTemplateId] = useState(null);
  const [updateLoading, setUpdateLoading] = useState(false);

  const templateOptions = allTemplates.map((template) => {
    return { label: template.name, value: template.id };
  });

  var templateMessage = null;
  if (selectedTemplateId !== null) {
    templateMessage = allTemplates.find(
      (t) => t.id === selectedTemplateId
    ).message;
  }

  // When user selects a template from the options dropdown.
  function handleTemplateOptionSelection(value, option) {
    setSelectedTemplateId(value);
  }

  // When a user clicks to update the template for given email.
  async function handleTemplateUpdateClick() {
    if (selectedTemplateId === null) {
      // No template selected, nothing to do here.
      return;
    }

    setUpdateLoading(true);
    const idToken = await user.getIdToken();
    const response = await fetch(
      "/api/v1/lead-research-reports/personalized-emails",
      {
        method: "POST",
        body: JSON.stringify({
          lead_research_report_id: lead_research_report_id,
          new_template_id: selectedTemplateId,
          personalized_email_id: emailId,
        }),
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer " + idToken,
        },
      }
    );
    const result = await response.json();
    if (result.status === "error") {
      throw result;
    }
    setUpdateLoading(false);
    const newTemplate = allTemplates.find((t) => t.id === selectedTemplateId);
    onEditSuccess(newTemplate);
  }

  return (
    <div className="email-template-edit-view">
      <Select
        options={templateOptions}
        onChange={handleTemplateOptionSelection}
      ></Select>
      {templateMessage && (
        <div className="message-container">
          <Text className="message-text">{addLineBreaks(templateMessage)}</Text>
        </div>
      )}
      <div className="btn-container">
        <Button
          className="cancel-btn"
          onClick={onCancel}
          disabled={updateLoading}
        >
          Cancel
        </Button>
        <Button
          className="update-btn"
          onClick={handleTemplateUpdateClick}
          loading={updateLoading}
          disabled={selectedTemplateId === null}
        >
          Update
        </Button>
      </div>
    </div>
  );
}

// Read mode view of current template.
function TemplateReadMode({ curEmailTemplate, onAllTemplatesFetched }) {
  // Logged in user.
  const { user } = useContext(AuthContext);
  const [allTemplatesLoading, setAllTemplatesLoading] = useState(false);

  // Handle edit template click by user.
  async function handleEditTemplateClick() {
    // Fetch all templates created by the given user.
    setAllTemplatesLoading(true);

    const idToken = await user.getIdToken();
    const response = await fetch("/api/v1/outreach-email-templates", {
      headers: { Authorization: "Bearer " + idToken },
    });
    const result = await response.json();
    if (result.status === "error") {
      throw result;
    }
    if (result.outreach_email_templates.length === 0) {
      const error_obj = {
        message: "No Templates found, please create templates first!",
        status_code: 400,
      };
      throw error_obj;
    }
    setAllTemplatesLoading(false);
    onAllTemplatesFetched(result.outreach_email_templates);
  }
  return (
    <div className="email-template-read-view">
      <Text className="text-label">Template: </Text>
      <Text>{curEmailTemplate !== null ? curEmailTemplate.name : "None"}</Text>
      <Button
        className="edit-email-template-icon"
        icon={<EditOutlined style={{ color: "#65558f" }} />}
        onClick={handleEditTemplateClick}
        loading={allTemplatesLoading}
      ></Button>
    </div>
  );
}

// Template Component inside the card
function Template({
  lead_research_report_id,
  emailId,
  curEmailTemplate,
  onTemplateChange,
}) {
  // Whether template is being edited or not.
  const [editTemplateMode, setEditTemplateMode] = useState(false);
  // All templates uploaded by user.
  const [allTemplates, setAllTemplates] = useState([]);

  function handleAllTemplatesFetched(fetchedTemplates) {
    // Update view to be in edit mode.
    setAllTemplates(fetchedTemplates);
    setEditTemplateMode(true);
  }

  // When a user cancels editing a template.
  function handleTemplateEditCancelled() {
    // Switch back to read view.
    setEditTemplateMode(false);
  }

  // Handler once template edit has happened on the backend.
  function handleTemplateEditSuccess(newTemplate) {
    onTemplateChange(newTemplate);
    setEditTemplateMode(false);
  }

  if (!editTemplateMode) {
    // Show read view of template.
    return (
      <TemplateReadMode
        curEmailTemplate={curEmailTemplate}
        onAllTemplatesFetched={handleAllTemplatesFetched}
      />
    );
  }

  // Show editable template view.
  return (
    <TemplateEditMode
      lead_research_report_id={lead_research_report_id}
      emailId={emailId}
      allTemplates={allTemplates}
      onCancel={handleTemplateEditCancelled}
      onEditSuccess={handleTemplateEditSuccess}
    />
  );
}

// A single EmailCard component.
function EmailCard({ lead_research_report_id, personalized_email }) {
  // Current template used in this email card.
  const [curEmailTemplate, setCurEmailTemplate] = useState(
    personalized_email.template
  );

  // Handler for when template is updated by the user.
  function handleTemplateUpdate(newTemplate) {
    setCurEmailTemplate(newTemplate);
  }

  // Helper method to get email body text from personalized email and report.
  function getEmailBodyText(personalized_email, email_template) {
    if (email_template === null || email_template.id === null) {
      // No template chosen, return only email opener.
      return personalized_email.email_opener;
    }

    // Return email opener as well as choen template.
    return personalized_email.email_opener + "\n\n" + email_template.message;
  }
  return (
    <Card>
      <div className="email-subject-container">
        <Text className="email-subject-label">Subject</Text>
        <div className="email-subject-text-container">
          <Text className="email-subject-text">
            {personalized_email.email_subject_line}
          </Text>
          <Text
            copyable={{
              text: personalized_email.email_subject_line,
              tooltips: ["Copy Subject"],
            }}
          ></Text>
        </div>
      </div>
      <div className="email-body-container">
        <Text className="email-body-label">Body</Text>
        <div className="email-body-text-container">
          <Text className="email-body-text">
            {addLineBreaks(
              getEmailBodyText(personalized_email, curEmailTemplate)
            )}
          </Text>
          <Text
            copyable={{
              text: getEmailBodyText(personalized_email, curEmailTemplate),
              tooltips: ["Copy Email Body"],
            }}
          ></Text>
        </div>
      </div>
      <div className="email-highlight-url-container">
        <Text className="source-label">Source:</Text>
        <Link href={personalized_email.highlight_url} target="_blank">
          {personalized_email.highlight_url}
        </Link>
      </div>
      <Template
        lead_research_report_id={lead_research_report_id}
        emailId={personalized_email.id}
        curEmailTemplate={curEmailTemplate}
        onTemplateChange={handleTemplateUpdate}
      />
    </Card>
  );
}

// Represents Personalized Emails to the lead.
function PersonalizedEmails({ lead_research_report_id, personalized_emails }) {
  return (
    <div id="personalized-emails-container">
      {personalized_emails.map((personalized_email) => (
        <EmailCard
          key={personalized_email.id}
          lead_research_report_id={lead_research_report_id}
          personalized_email={personalized_email}
        />
      ))}
    </div>
  );
}

export default PersonalizedEmails;
