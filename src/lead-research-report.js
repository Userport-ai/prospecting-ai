import "./lead-research-report.css";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { Flex, Typography, Button, Card, Tabs, Empty, Skeleton } from "antd";
import { useNavigate, useLoaderData, useNavigation } from "react-router-dom";
import { useContext, useState } from "react";
import SelectTemplateModal from "./select-template-modal";
import { AuthContext } from "./root";
import {
  getUserFromServer,
  isUserOnboarding,
  stateAfterViewedPersonalizedEmails,
  updateUserStateOnServer,
  userHasNotViewedPersonalizedEmail,
} from "./helper-functions";
import OnboardingProgressBar from "./onboarding-progress-bar";

const { Text, Link } = Typography;

// Replace newlines with HTML break tags.
function addLineBreaks(text) {
  return text.split("\n").map((substr) => {
    return (
      <>
        {substr}
        <br />
      </>
    );
  });
}

// Represents Personalized Emails to the lead.
function PersonalizedEmails({
  chosen_outreach_email_template,
  personalized_emails,
}) {
  // Helper to get email body text from personalized email and report.
  function getEmailBodyText(
    personalized_email,
    chosen_outreach_email_template
  ) {
    if (chosen_outreach_email_template.id === null) {
      // No template chosen, return only email opener.
      return personalized_email.email_opener;
    }

    // Return email opener as well as choen template.
    return (
      personalized_email.email_opener +
      "\n\n" +
      chosen_outreach_email_template.message
    );
  }

  // A single EmailCard component.
  function EmailCard({ personalized_email, chosen_outreach_email_template }) {
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
                getEmailBodyText(
                  personalized_email,
                  chosen_outreach_email_template
                )
              )}
            </Text>
            <Text
              copyable={{
                text: getEmailBodyText(
                  personalized_email,
                  chosen_outreach_email_template
                ),
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
      </Card>
    );
  }

  return (
    <div id="personalized-emails-with-title-container">
      <h1>Emails</h1>
      <div id="personalized-emails-container">
        {personalized_emails.map((personalized_email) => (
          <EmailCard
            key={personalized_email.id}
            personalized_email={personalized_email}
            chosen_outreach_email_template={chosen_outreach_email_template}
          />
        ))}
      </div>
    </div>
  );
}

// The email template selected for given lead.
function SelectedEmailTemplate({
  chosen_outreach_email_template,
  onTemplateSelection,
}) {
  const { user } = useContext(AuthContext);
  const [modalOpen, setModalOpen] = useState(false);
  const [outreachTemplates, setOutreachTemplates] = useState([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);

  // Create modal to allow user to select template.
  async function selectTemplateModal() {
    // Fetch list of templates created by the given user.
    setTemplatesLoading(true);
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
    setOutreachTemplates(result.outreach_email_templates);
    setTemplatesLoading(false);
    setModalOpen(true);
  }

  function onTemplateOk(templateId) {
    setModalOpen(false);
    onTemplateSelection(templateId);
  }

  function onTemplateCancel() {
    setModalOpen(false);
  }

  var selectedTemplateView = null;
  if (chosen_outreach_email_template.id === null) {
    // No template was chosen, return empty data.
    selectedTemplateView = (
      <div id="no-template-selected">
        <Empty description={<Text>No Template matched</Text>}>
          <Button onClick={selectTemplateModal} loading={templatesLoading}>
            Add a template
          </Button>
        </Empty>
      </div>
    );
  } else {
    // Show selected template.
    selectedTemplateView = (
      <>
        <Button
          id="change-email-template-btn"
          onClick={selectTemplateModal}
          loading={templatesLoading}
          disabled={templatesLoading}
        >
          Change Template
        </Button>
        <Card key="selected-template-card-key" id="email-template-card">
          <div id="template-name-container">
            <Text className="card-text-label" strong>
              Name:
            </Text>
            <Text className="template-text">
              {chosen_outreach_email_template.name}
            </Text>
          </div>
          <div id="template-message-container">
            <Text className="card-text-label" strong>
              Message
            </Text>
            <Text className="template-text">
              {addLineBreaks(chosen_outreach_email_template.message)}
            </Text>
          </div>
        </Card>
      </>
    );
  }

  return (
    <div id="selected-email-template-with-title-container">
      <SelectTemplateModal
        modalOpen={modalOpen}
        outreachTemplates={outreachTemplates}
        onSelect={onTemplateOk}
        onCancel={onTemplateCancel}
      />
      <h1>Selected Email Template</h1>
      {selectedTemplateView}
    </div>
  );
}

// Represents selected Email Template and Personalized Emails generated for the lead.
function EmailTemplateAndPersonalizedEmails(props) {
  const { user } = useContext(AuthContext);
  const [chosen_outreach_email_template, setOutreachTemplate] = useState(
    props.chosen_outreach_email_template
  );
  const [personalized_emails, setPersonalizedEmails] = useState(
    props.personalized_emails
  );
  const [templateUpdating, setTemplateUpdating] = useState(false);

  //Updates new template in report on selection by user.
  async function updateNewTemplate(templateId) {
    setTemplateUpdating(true);
    const idToken = await user.getIdToken();
    const response = await fetch("/api/v1/lead-research-reports/template", {
      method: "POST",
      body: JSON.stringify({
        lead_research_report_id: props.lead_research_report_id,
        selected_template_id: templateId,
      }),
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + idToken,
      },
    });
    const result = await response.json();
    if (result.status === "error") {
      throw result;
    }
    setOutreachTemplate(result.chosen_outreach_email_template);
    setPersonalizedEmails(result.personalized_emails);
    setTemplateUpdating(false);
  }

  if (templateUpdating) {
    // Show skeleton with loading screen while template and emails are updating.
    return (
      <>
        <Flex vertical={false} justify="center">
          <h3>
            Updating template and emails. This can take a few minutes, please
            wait.
          </h3>
        </Flex>
        <Skeleton
          active
          paragraph={{
            rows: 15,
          }}
        />
      </>
    );
  }

  return (
    <>
      <SelectedEmailTemplate
        chosen_outreach_email_template={chosen_outreach_email_template}
        onTemplateSelection={updateNewTemplate}
      />
      <PersonalizedEmails
        chosen_outreach_email_template={chosen_outreach_email_template}
        personalized_emails={personalized_emails}
      />
    </>
  );
}

// Represents Highlight from the leads' news.
function Highlight({ highlight }) {
  return (
    <Card>
      <div>
        <Text strong className="card-category">
          {highlight.category_readable_str}
        </Text>
      </div>
      <div className="card-citation-link-container">
        <Text className="card-citation-source-label" strong>
          Source:{" "}
        </Text>
        <Link
          className="card-citation-link"
          href={highlight.url}
          target="_blank"
        >
          {highlight.url}
        </Link>
      </div>
      <div className="card-date-container">
        <Text className="card-date-label" strong>
          Publish Date:{" "}
        </Text>
        <Text className="card-date">{highlight.publish_date_readable_str}</Text>
      </div>
      <div className="card-text-container">
        <Text className="card-text-label" strong>
          Summary
        </Text>
        <Text className="card-text">{highlight.concise_summary}</Text>
      </div>
    </Card>
  );
}

// Represents Categories buttons and associated highlights.
function CategoriesAndHighlights({ details }) {
  var initialSelectedCategories = [];
  if (details.length > 0) {
    initialSelectedCategories = [details[0].category_readable_str];
  }
  const [categoriesSelected, setCategoriesSeleted] = useState(
    initialSelectedCategories
  );

  function handleCategoryClicked(category) {
    if (categoriesSelected.filter((cat) => cat === category).length === 0) {
      // Category not selected yet, prepend to selection.
      setCategoriesSeleted([category, ...categoriesSelected]);
    } else {
      // Category already selected, remove it.
      setCategoriesSeleted(
        categoriesSelected.filter((cat) => cat !== category)
      );
    }
  }

  return (
    <>
      {/* These are the categories */}
      {details.map((detail) => {
        let categoryBtnClass = categoriesSelected.includes(
          detail.category_readable_str
        )
          ? "category-btn-selected"
          : "category-btn";
        return (
          <Button
            key={detail.category}
            className={categoryBtnClass}
            type="primary"
            onClick={(e) => handleCategoryClicked(e.target.innerText)}
          >
            {detail.category_readable_str}
          </Button>
        );
      })}
      {/* These are the highlights from selected categories. */}
      {categoriesSelected
        .map(
          (selectedCategory) =>
            // Filtered category guaranteed to exist and size 1 since selected categories
            // are from the same details array.
            details.filter(
              (detail) => detail.category_readable_str === selectedCategory
            )[0]
        )
        .flatMap((detail) =>
          detail.highlights.map((highlight) => (
            <Highlight key={highlight.id} highlight={highlight} />
          ))
        )}
    </>
  );
}

function RecentNews({ details }) {
  return (
    <Flex id="report-details-container" vertical={false} wrap gap="large">
      <CategoriesAndHighlights details={details} />
    </Flex>
  );
}

function ReportHeader({ report }) {
  const navigate = useNavigate();
  return (
    <div id="header">
      <div id="back-arrow">
        <ArrowLeftOutlined onClick={() => navigate("/")} />
      </div>
      <div id="person-details-container">
        <div id="person-details">
          <h1 id="person-name">{report.person_name}</h1>
          <h3 id="role-title">
            {report.person_role_title}, {report.company_name}
          </h3>
          <Link
            id="linkedin-url"
            href={report.person_linkedin_url}
            target="_blank"
          >
            {report.person_linkedin_url}
          </Link>
        </div>
      </div>
      <div id="report-dates">
        <div id="report-creation-date">
          <Text className="report-dates-label">Report Creation Date: </Text>
          <Text strong>{report.report_creation_date_readable_str}</Text>
        </div>
        <div id="research-start-date">
          <Text className="report-dates-label">Research Start Date: </Text>
          <Text strong> {report.report_publish_cutoff_date_readable_str}</Text>
        </div>
      </div>
    </div>
  );
}

// Loader to fetch research report for given lead.
export const leadResearchReportLoader = (authContext) => {
  return async ({ params }) => {
    const { user } = authContext;
    if (!user) {
      // User is logged out.
      return null;
    }
    const idToken = await user.getIdToken();
    const response = await fetch("/api/v1/lead-research-reports/" + params.id, {
      headers: { Authorization: "Bearer " + idToken },
    });
    const result = await response.json();
    if (result.status === "error") {
      console.log("Error getting lead report: ", result);
      throw result;
    }
    return result;
  };
};

// Main Component.
function LeadResearchReport() {
  const loaderResponse = useLoaderData();
  const report = loaderResponse.lead_research_report;
  const [userFromServer, setUserFromServer] = useState(loaderResponse.user);
  const component_is_loading = useNavigation().state !== "idle";
  const { user } = useContext(AuthContext);

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

  // Helper to get tab key for Recent News tab.
  function recentNewsTabKey() {
    return "1";
  }

  // Helper to get tab key for Personalized Email tab.
  function personalizedEmailsTabKey() {
    return "2";
  }

  // Handler for when user changes tab.
  async function onActiveTabChange(activeKey) {
    if (
      activeKey !== recentNewsTabKey() &&
      activeKey !== personalizedEmailsTabKey()
    ) {
      const error_obj = {
        message: `Invalid Tab key value: ${activeKey}`,
        status_code: 500,
      };
      throw error_obj;
    }

    if (
      activeKey === personalizedEmailsTabKey() &&
      userHasNotViewedPersonalizedEmail(userFromServer.state)
    ) {
      // First time user is viewing personalized emails, update the user state on server and then the UI.
      // User is onboarded now.
      const idToken = await user.getIdToken();
      await updateUserStateOnServer(
        stateAfterViewedPersonalizedEmails(),
        idToken
      );
      const gotUserFromServer = await getUserFromServer(idToken);
      setUserFromServer(gotUserFromServer);
    }
  }

  return (
    <div id="lead-research-report-outer">
      {isUserOnboarding(userFromServer) && (
        <OnboardingProgressBar userFromServer={userFromServer} />
      )}
      <div id="lead-research-report-container">
        <ReportHeader report={report} />
        <Tabs
          onChange={onActiveTabChange}
          items={[
            {
              label: <h1>Recent News</h1>,
              key: recentNewsTabKey(),
              children: <RecentNews details={report.details} />,
            },
            {
              label: <h1>Personalized Emails</h1>,
              key: personalizedEmailsTabKey(),
              children: (
                <EmailTemplateAndPersonalizedEmails
                  lead_research_report_id={report.id}
                  chosen_outreach_email_template={
                    report.chosen_outreach_email_template
                  }
                  personalized_emails={report.personalized_emails}
                />
              ),
            },
          ]}
        />
      </div>
    </div>
  );
}

export default LeadResearchReport;
