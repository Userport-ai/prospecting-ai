import "./login.css";
import { Button } from "antd";

function Login() {
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
        <Button id="login-btn" onClick={() => console.log("test")}>
          Sign In
        </Button>
      </div>
    </div>
  );
}

export default Login;
