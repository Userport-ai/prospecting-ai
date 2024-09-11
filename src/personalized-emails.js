import "./personalized-emails.css";
import { addLineBreaks } from "./helper-functions";
import { Card, Typography } from "antd";

const { Text, Link } = Typography;

// A single EmailCard component.
function EmailCard({ personalized_email, chosen_outreach_email_template }) {
  // Helper to get email body text from personalized email and report.
  function getEmailBodyText(
    personalized_email,
    chosen_outreach_email_template
  ) {
    if (
      chosen_outreach_email_template === null ||
      chosen_outreach_email_template.id === null
    ) {
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
      <div className="email-template-used">
        <Text className="text-label">Template: </Text>
        <Text>{chosen_outreach_email_template.name}</Text>
      </div>
    </Card>
  );
}

// Represents Personalized Emails to the lead.
function PersonalizedEmails({
  chosen_outreach_email_template,
  personalized_emails,
}) {
  return (
    <div id="personalized-emails-container">
      {personalized_emails.map((personalized_email) => (
        <EmailCard
          key={personalized_email.id}
          personalized_email={personalized_email}
          chosen_outreach_email_template={chosen_outreach_email_template}
        />
      ))}
    </div>
  );
}

export default PersonalizedEmails;
