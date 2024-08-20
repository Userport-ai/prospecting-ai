// Module with just helper functions used by the App.

// Takes User object returned by server (NOT Firebase) and returns true if user is still onboarding and false otherwise.
export function isUserOnboarding(userFromServer) {
  const userState = userFromServer.state;
  return userState !== "viewed_personalized_emails" ? true : false;
}

// Returns true if given user state has not created a template yet and false otherwise.
export function userHasNotCreatedTemplate(userState) {
  return userState === "new_user" ? true : false;
}

// Returns user state after first template creation is successful.
export function stateAfterFirstTemplateCreation() {
  return "created_first_template";
}
