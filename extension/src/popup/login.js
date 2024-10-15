/*global chrome*/
import { getCurrentTab } from "./helper";
import "./login.css";
import { Button } from "antd";

function Login() {
  // Handle click by user to login.
  async function handleLoginClick() {
    // Chrome runtime exists only when called inside extension.
    if (chrome.runtime) {
      const tab = await getCurrentTab();
      if (tab === null) {
        return;
      }

      // Send message to service worker to start login.
      chrome.runtime.sendMessage({ action: "login-user", tabId: tab.id });
    }
  }

  return (
    <div id="login-container">
      <div id="logo-container">
        <img
          src="/combination_mark_primary.png"
          alt="userport-combination-mark"
        />
      </div>
      <div id="tagline-container">
        <h4 id="tagline">Research and Personalize Outreach using AI</h4>
      </div>
      <div id="login-btn-container">
        <Button id="login-btn" onClick={handleLoginClick}>
          Sign In
        </Button>
      </div>
    </div>
  );
}

export default Login;
