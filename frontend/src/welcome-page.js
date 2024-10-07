import "./welcome-page.css";
import { Button, Typography } from "antd";
import { useContext, useState } from "react";
import { AuthContext } from "./root";
import { useNavigate } from "react-router-dom";
import {
  stateAfterViewingWelcomePage,
  updateUserStateOnServer,
} from "./helper-functions";

const { Text } = Typography;

// Welcome User the first time they sign in.
function WelcomePage() {
  const { user } = useContext(AuthContext);
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  async function handleGetStartedClick() {
    setLoading(true);
    const idToken = await user.getIdToken();
    await updateUserStateOnServer(stateAfterViewingWelcomePage(), idToken);
    // Go to /templates so user can create their first template.
    return navigate("/templates");
  }

  return (
    <div id="welcome-page-outer-container">
      <div id="welcome-page-container">
        <div id="title-and-tagline-container">
          <h1 id="title-text">Welcome to Userport, {user.displayName}!</h1>
          <Text id="tagline">
            We help you personalize your outreach using AI.
          </Text>
        </div>
        <Button
          id="get-started-btn"
          loading={loading}
          disabled={loading}
          onClick={handleGetStartedClick}
        >
          Get Started
        </Button>
      </div>
    </div>
  );
}

export default WelcomePage;
