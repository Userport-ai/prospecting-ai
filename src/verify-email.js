import "./verify-email.css";
import { getAuth, sendEmailVerification } from "firebase/auth";
import { useContext, useState } from "react";
import { Button, Layout, Spin, Typography, Alert } from "antd";
import { AuthContext } from "./root";
import { Navigate, useNavigate, useNavigation } from "react-router-dom";

const { Header } = Layout;
const { Text } = Typography;

function VerifyEmail() {
  const { user } = useContext(AuthContext);
  const [emailSent, setEmailSent] = useState(false);
  const navigate = useNavigate();
  const component_is_loading = useNavigation().state !== "idle";

  if (!user) {
    // User is logged out, redirect to login page.
    return <Navigate to="/login" replace />;
  }

  if (user.emailVerified) {
    // User email already verified, redirect to logged in.
    return <Navigate to="/logged-in" replace />;
  }

  function VerifyEmailStep({ onEmailSent }) {
    const [sendingEmail, setSendingEmail] = useState(false);
    // Sends email confirmation to user's email.
    async function handleSendEmailClick() {
      setSendingEmail(true);
      await sendEmailVerification(user);
      setSendingEmail(false);
      onEmailSent();
    }

    return (
      <>
        <Text id="verify-email-instructions">
          A verification email will be sent to your email when you click the
          button below.
        </Text>
        <Button
          id="email-verification-button"
          loading={sendingEmail}
          disabled={sendingEmail}
          onClick={handleSendEmailClick}
        >
          Send Verification Email
        </Button>
      </>
    );
  }

  function ConfirmEmailVerfiied({ onEmailConfirmation }) {
    const [loading, setLoading] = useState(false);
    const [confirmationError, setConfirmationError] = useState(false);

    // Check if user email has actaully been verified.
    async function handleConfirmClick() {
      setLoading(true);
      setConfirmationError(false);

      // Reload user.
      await getAuth().currentUser.reload();

      if (getAuth().currentUser.emailVerified) {
        setLoading(false);
        onEmailConfirmation();
      } else {
        setLoading(false);
        setConfirmationError(true);
        setInterval(() => setConfirmationError(false), 3000);
      }
    }

    return (
      <>
        <Text id="confirm-email-instructions">
          Confirm that you have verified your email.
        </Text>
        {confirmationError && (
          <Alert
            message="Email Confirmation failed, please try again."
            type="error"
            showIcon
          />
        )}
        <Button
          id="email-confirm-button"
          loading={loading}
          disabled={loading}
          onClick={handleConfirmClick}
        >
          Confirm
        </Button>
      </>
    );
  }

  return (
    <>
      <Header id="verify-email-header" />
      <Spin spinning={component_is_loading} fullscreen />
      <div id="verify-email-page-container">
        <div id="verify-email-container">
          <div id="verify-email-title-container">
            <h1>Verify your Email</h1>
          </div>
          {emailSent ? (
            <ConfirmEmailVerfiied
              onEmailConfirmation={() => navigate("/leads")}
            />
          ) : (
            <VerifyEmailStep onEmailSent={() => setEmailSent(true)} />
          )}
        </div>
      </div>
    </>
  );
}

export default VerifyEmail;
