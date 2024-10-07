// Module with just helper functions used by the App.

// Returns true if app is running locally and false if it is deployed (in React terminology: production).
export function isLocalEnv() {
  return process.env.NODE_ENV === "development";
}

// Takes User object returned by server (NOT Firebase) and returns true if user is still onboarding and false otherwise.
export function isUserOnboarding(userFromServer) {
  const userState = userFromServer.state;
  return userState !== "viewed_personalized_emails" ? true : false;
}

// Returns true if given user state has not seen Welcome Page yet and false otherwise.
export function userHasNotViewedWelcomePage(userState) {
  return userState === "new_user" ? true : false;
}

// Returns true if given user state has not created a template yet and false otherwise.
export function userHasNotCreatedTemplate(userState) {
  return userState === "viewed_welcome_page" ? true : false;
}

// Returns true if given user state has not created a lead yet and false otherwise.
export function userHasNotCreatedLead(userState) {
  return userState === "created_first_template" ? true : false;
}

// Returns true if given user state has not viwed personalized emails yet and false otherwise.
export function userHasNotViewedPersonalizedEmail(userState) {
  return userState === "added_first_lead" ? true : false;
}

// Returns user state after viewing welcome page is successful.
export function stateAfterViewingWelcomePage() {
  return "viewed_welcome_page";
}

// Returns user state after first template creation is successful.
export function stateAfterFirstTemplateCreation() {
  return "created_first_template";
}

// Returns user state after first lead creation is successful.
export function stateAfterFirstLeadCreation() {
  return "added_first_lead";
}

// Returns user state after personalized emails are viewed.
export function stateAfterViewedPersonalizedEmails() {
  return "viewed_personalized_emails";
}

// Function that updates user state on the server and returns the result.
// Throws an error if the update failed.
export async function updateUserStateOnServer(newState, idToken) {
  const response = await fetch("/api/v1/users", {
    method: "PUT",
    body: JSON.stringify({ state: newState }),
    headers: {
      "Content-Type": "application/json",
      Authorization: "Bearer " + idToken,
    },
  });

  const result = await response.json();
  if (result.status === "error") {
    throw result;
  }
  return result;
}

// Fetches User object from the server.
// Throws an error if the fetch failed.
export async function getUserFromServer(idToken) {
  const response = await fetch("/api/v1/users", {
    headers: { Authorization: "Bearer " + idToken },
  });
  const result = await response.json();
  if (result.status === "error") {
    throw result;
  }
  return result.user;
}

// Replace newlines with HTML break tags.
export function addLineBreaks(text) {
  if (text === null) {
    return null;
  }
  return text.split("\n").map((substr) => {
    return (
      <>
        {substr}
        <br />
      </>
    );
  });
}
