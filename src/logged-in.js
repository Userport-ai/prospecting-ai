// Loader that the user is directed to after sign in or log in.

import { redirect } from "react-router-dom";
import {
  getUserFromServer,
  userHasNotCreatedTemplate,
} from "./helper-functions";

// This is the loader that is
export const loggedInLoader = (authContext) => {
  return async () => {
    // Get Firebase User object from Context.
    const { user } = authContext;
    if (!user) {
      // User is logged out.
      return null;
    }
    if (!user.emailVerified) {
      // If user email is not verified, redirect to verification.
      return redirect("/verify-email");
    }
    const idToken = await user.getIdToken();
    const userFromServer = await getUserFromServer(idToken);
    if (userHasNotCreatedTemplate(userFromServer.state)) {
      // Redirect to /templates so they can first create a template.
      return redirect("/templates");
    }
    // Default to redirect them to leads page.
    return redirect("/leads");
  };
};
