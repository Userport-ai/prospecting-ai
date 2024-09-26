import "./personalized-emails.css";
import { addLineBreaks } from "./helper-functions";
import {
  Card,
  Typography,
  Button,
  Select,
  message,
  Input,
  Tooltip,
} from "antd";
import {
  EditOutlined,
  CopyOutlined,
  CheckOutlined,
  CloseOutlined,
} from "@ant-design/icons";
import { useContext, useState } from "react";
import { AuthContext } from "./root";
import { usePostHog } from "posthog-js/react";

const { Text, Link } = Typography;
const { TextArea } = Input;

// Helper to update Personalized email by calling the backend server.
async function updateEmailOnBackend(
  posthog,
  user,
  lead_research_report_id,
  emailId,
  new_template_id = null,
  newEmailOpener = null,
  newEmailSubjectLine = null
) {
  const idToken = await user.getIdToken();
  const response = await fetch(
    "/api/v1/lead-research-reports/personalized-emails/" + emailId,
    {
      method: "PUT",
      body: JSON.stringify({
        lead_research_report_id: lead_research_report_id,
        new_template_id: new_template_id,
        new_email_opener: newEmailOpener,
        new_email_subject_line: newEmailSubjectLine,
      }),
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + idToken,
      },
    }
  );
  if (!response.ok) {
    // Send event.
    posthog.capture("p_email_update_failed", {
      email_id: emailId,
      template_id: new_template_id,
      report_id: lead_research_report_id,
      email_opener: newEmailOpener,
      email_subject_line: newEmailSubjectLine,
      status_code: response.status,
      status_text: response.statusText,
    });
  }
  const result = await response.json();
  if (result.status === "error") {
    throw result;
  }
}

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
  const posthog = usePostHog();

  const templateOptions = allTemplates.map((template) => {
    return { label: template.name, value: template.id };
  });

  var templateMessage = null;
  if (selectedTemplateId !== null) {
    templateMessage = allTemplates.find((t) => t.id === selectedTemplateId)
      .messages[0];
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
    await updateEmailOnBackend(
      posthog,
      user,
      lead_research_report_id,
      emailId,
      selectedTemplateId,
      null,
      null
    );
    setUpdateLoading(false);

    // We need to convert from OutreachEmailTemplate object to ChosenOutreachEmailTemplate (which is stored in PersonalizedEmail object).
    const newOutreachTemplate = allTemplates.find(
      (t) => t.id === selectedTemplateId
    );
    const chosenOutreachTemplate = {
      id: newOutreachTemplate.id,
      creation_date: newOutreachTemplate.creation_date,
      name: newOutreachTemplate.name,
      message: newOutreachTemplate.messages[0],
    };
    onEditSuccess(chosenOutreachTemplate);

    // Send event.
    posthog.capture("p_email_template_updated", {
      email_id: emailId,
      template_id: selectedTemplateId,
      report_id: lead_research_report_id,
    });
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
  // All templates uploaded by user. These are outreach email templates and
  // not the template object stored within PersonalizedEmail object.
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

// Email Subject Line component that is editable.
function EmailSubjectLine({
  lead_research_report_id,
  emailId,
  emailSubjectLine,
  onEditSuccess,
}) {
  // Logged in user.
  const { user } = useContext(AuthContext);
  const [readOnlyMode, setReadOnlyMode] = useState(true);
  const origText = emailSubjectLine;
  const [curEmailSubjectLine, setCurEmailSubjectLine] =
    useState(emailSubjectLine);
  const [updateLoading, setUpdateLoading] = useState(false);
  const posthog = usePostHog();

  // When user confirms update to email opener. Send update to server.
  async function handleUpdate() {
    setUpdateLoading(true);
    await updateEmailOnBackend(
      posthog,
      user,
      lead_research_report_id,
      emailId,
      null,
      null,
      curEmailSubjectLine
    );
    setUpdateLoading(false);
    setReadOnlyMode(true);
    onEditSuccess(curEmailSubjectLine);

    // Send event.
    posthog.capture("p_email_subject_edited", {
      email_id: emailId,
      report_id: lead_research_report_id,
    });
  }

  if (readOnlyMode) {
    return (
      <>
        <Text className="email-subject-text">{emailSubjectLine}</Text>
        <EditOutlined onClick={() => setReadOnlyMode(false)} />
      </>
    );
  }

  return (
    <div className="edit-subject-container">
      <Input
        className="email-subject-text"
        value={curEmailSubjectLine}
        onChange={(e) => setCurEmailSubjectLine(e.target.value)}
        disabled={updateLoading}
      />
      <div className="btns-container">
        <Tooltip title="Cancel">
          <Button
            icon={<CloseOutlined />}
            onClick={() => {
              setCurEmailSubjectLine(origText);
              setReadOnlyMode(true);
            }}
            disabled={updateLoading}
          />
        </Tooltip>
        <Tooltip title="Update">
          <Button
            icon={<CheckOutlined />}
            onClick={handleUpdate}
            loading={updateLoading}
            disabled={updateLoading}
          />
        </Tooltip>
      </div>
    </div>
  );
}

// Email Opener component that is editable.
function EmailOpener({
  lead_research_report_id,
  emailId,
  emailOpener,
  onEditSuccess,
}) {
  // Logged in user.
  const { user } = useContext(AuthContext);
  const [readOnlyMode, setReadOnlyMode] = useState(true);
  const origText = emailOpener;
  const [curEmailOpener, setCurEmailOpener] = useState(emailOpener);
  const [updateLoading, setUpdateLoading] = useState(false);
  const posthog = usePostHog();

  // When user confirms update to email opener. Send update to server.
  async function handleUpdate() {
    setUpdateLoading(true);
    await updateEmailOnBackend(
      posthog,
      user,
      lead_research_report_id,
      emailId,
      null,
      curEmailOpener,
      null
    );
    setUpdateLoading(false);
    setReadOnlyMode(true);
    onEditSuccess(curEmailOpener);

    // Send Event.
    posthog.capture("p_email_opener_edited", {
      email_id: emailId,
      report_id: lead_research_report_id,
    });
  }

  if (readOnlyMode) {
    return (
      <>
        <Text className="email-body-text">{addLineBreaks(curEmailOpener)}</Text>
        <EditOutlined onClick={() => setReadOnlyMode(false)} />
      </>
    );
  }

  return (
    <div className="edit-opener-container">
      <TextArea
        className="email-body-text"
        autoSize={true}
        value={curEmailOpener}
        onChange={(e) => setCurEmailOpener(e.target.value)}
        disabled={updateLoading}
      />
      <div className="btns-container">
        <Tooltip title="Cancel">
          <Button
            icon={<CloseOutlined />}
            onClick={() => {
              setCurEmailOpener(origText);
              setReadOnlyMode(true);
            }}
            disabled={updateLoading}
          />
        </Tooltip>
        <Tooltip title="Update">
          <Button
            icon={<CheckOutlined />}
            onClick={handleUpdate}
            loading={updateLoading}
            disabled={updateLoading}
          />
        </Tooltip>
      </div>
    </div>
  );
}

// A single EmailCard component.
function EmailCard({ lead_research_report_id, personalized_email }) {
  // Current template used in this email card.
  const [curEmailTemplate, setCurEmailTemplate] = useState(
    personalized_email.template
  );
  const [emailSubjectLine, setEmailSubjectLine] = useState(
    personalized_email.email_subject_line
  );
  const [emailOpener, setEmailOpener] = useState(
    personalized_email.email_opener
  );
  const [messageApi, contextHolder] = message.useMessage();
  const posthog = usePostHog();

  // Handle email subject Line being edited successfully by the user.
  async function handleEmailSubjectLineEdited(newEmailSubjectLine) {
    setEmailSubjectLine(newEmailSubjectLine);
  }

  // Handler when user copies email subject line.
  async function handleEmailSubjectCopied() {
    // Copy to clipboard.
    navigator.clipboard.writeText(emailSubjectLine);

    // Show message to prompt.
    messageApi.open({
      type: "success",
      content: "Copied Email Subject Line",
      duration: 3,
    });

    // Send event.
    posthog.capture("user_p_email_subject_copied", {
      email_id: personalized_email.id,
      report_id: lead_research_report_id,
    });
  }

  // Handle email opener being edited successfully by the user.
  async function handleEmailOpenerEdited(newEmailOpener) {
    setEmailOpener(newEmailOpener);
  }

  // Helper method to get email body text from personalized email and report.
  function getEmailBodyText(emailOpener, email_template) {
    if (email_template === null || email_template.id === null) {
      // No template chosen, return only email opener.
      return emailOpener;
    }

    // Return email opener as well as choen template.
    return emailOpener + "\n\n" + email_template.message;
  }

  // Handler when user copies email body message.
  async function handleEmailBodyCopied() {
    // Copy to clipboard.
    navigator.clipboard.writeText(
      getEmailBodyText(emailOpener, curEmailTemplate)
    );

    // Show message to prompt.
    messageApi.open({
      type: "success",
      content: "Copied Email Body",
      duration: 3,
    });

    // Send event.
    posthog.capture("user_p_email_body_copied", {
      email_id: personalized_email.id,
      report_id: lead_research_report_id,
    });
  }

  // Handler for when template is updated by the user.
  function handleTemplateUpdate(newTemplate) {
    setCurEmailTemplate(newTemplate);
  }

  return (
    <Card>
      {contextHolder}
      <div className="email-subject-container">
        <Text className="email-subject-label">Subject</Text>
        {/* Display Email subject Line. Editable. */}
        <div className="email-subject-text-container">
          <EmailSubjectLine
            lead_research_report_id={lead_research_report_id}
            emailId={personalized_email.id}
            emailSubjectLine={emailSubjectLine}
            onEditSuccess={handleEmailSubjectLineEdited}
          />
          <CopyOutlined onClick={handleEmailSubjectCopied} />
        </div>
      </div>
      <div className="email-body-container">
        <Text className="email-body-label">Body</Text>
        <div className="email-body-text-container">
          {/* Display Email Opener. Editable. */}
          <div className="email-opener-container">
            <EmailOpener
              lead_research_report_id={lead_research_report_id}
              emailId={personalized_email.id}
              emailOpener={emailOpener}
              onEditSuccess={handleEmailOpenerEdited}
            />
            <CopyOutlined onClick={handleEmailBodyCopied} />
          </div>
          {/* Display Template. Not editable here, separate button below to edit it. */}
          <Text className="email-body-text">
            {curEmailTemplate && addLineBreaks(curEmailTemplate.message)}
          </Text>
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
  // Sort personalized emails by the most recently updated ones.
  personalized_emails.sort((e1, e2) => {
    return new Date(e2.last_updated_date) - new Date(e1.last_updated_date);
  });
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
