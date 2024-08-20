import { Steps, ConfigProvider } from "antd";
import "./onboarding-progress-bar.css";

function OnboardingProgressBar({ userFromServer }) {
  const userState = userFromServer.state;
  var currentValue = 0;
  var currentStatus = "process";
  if (userState === "viewed_welcome_page") {
    currentValue = 0;
  } else if (userState === "created_first_template") {
    currentValue = 1;
  } else if (userState === "added_first_lead") {
    currentValue = 2;
  } else if (userState === "viewed_personalized_emails") {
    currentStatus = "finish";
  }
  return (
    <div id="onboarding-progress-outer-container">
      <div id="onboarding-progress-steps-container">
        <ConfigProvider
          theme={{
            token: {
              // Styling for buttons.
              // Seed Token
              colorPrimary: "#65558f",
            },
          }}
        >
          <Steps
            current={currentValue}
            status={currentStatus}
            items={[
              {
                title: "Create your first email template",
              },
              {
                title: "Add your first lead",
              },
              {
                title: "View Personalized Emails",
              },
            ]}
          ></Steps>
        </ConfigProvider>
      </div>
    </div>
  );
}

export default OnboardingProgressBar;
