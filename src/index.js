import React, { useContext } from "react";
import ReactDOM from "react-dom/client";
import Root, { AuthContext } from "./root";
import App from "./App";
import Login, { loginLoader } from "./login";
import AllTemplates from "./all-templates";
import { templateMessagesLoader } from "./all-templates";
import CreateOrEditTemplateMessage, {
  createOrEditTemplateLoader,
} from "./create-or-edit-template";
import { createOrEditTemplateAction } from "./create-or-edit-template";
import Leads from "./leads";
import { leadsLoader } from "./leads";
import EnterLeadInfo, { enterLeadInfoLoader } from "./enter-lead-info";
import { enterLeadAction } from "./enter-lead-info";
import LeadResearchReport from "./lead-research-report";
import { leadResearchReportLoader } from "./lead-research-report";
import ErrorPage from "./error-page";
import {
  createBrowserRouter,
  redirect,
  RouterProvider,
} from "react-router-dom";
import reportWebVitals from "./reportWebVitals";
// Do not remove bootstrap, it is likely used a dependency by libraries.
import "bootstrap/dist/css/bootstrap.css";
// Put any other imports below so that CSS from your
// components takes precedence over default styles.
import "./index.css";
import EnteredLeadSuccess, {
  enteredLeadSuccessLoader,
} from "./entered-lead-success";
import VerifyEmail from "./verify-email";
import { loggedInLoader } from "./logged-in";
import WelcomePage from "./welcome-page";
import { isLocalEnv } from "./helper-functions";
import { PostHogProvider } from "posthog-js/react";

const postHogOptions = {
  api_host: process.env.REACT_APP_PUBLIC_POSTHOG_HOST,
};

// Enables mocking only for local env, disabled in production and test.
async function enableMocking() {
  return;
  if (!isLocalEnv()) {
    return;
  }
  const { worker } = await import("./mocks/browser");
  //  `worker.start()` returns a Promise that resolves
  // once the Service Worker is up and ready to intercept requests.
  return worker.start();
}

function AppRoutes() {
  const authContext = useContext(AuthContext);
  if (authContext.isAuthLoading) {
    // User auth is still loading, don't render app.
    return <div></div>;
  }

  const router = (context) =>
    createBrowserRouter([
      {
        path: "/login",
        element: <Login />,
        errorElement: <ErrorPage />,
        loader: loginLoader(context),
      },
      {
        path: "/verify-email",
        element: <VerifyEmail />,
        errorElement: <ErrorPage />,
      },
      {
        path: "/logged-in",
        errorElement: <ErrorPage />,
        loader: loggedInLoader(context),
      },
      {
        path: "/",
        element: <App />,
        errorElement: <ErrorPage />,
        children: [
          {
            path: "/",
            loader: () => redirect("/leads"),
          },
          {
            path: "/welcome",
            element: <WelcomePage />,
          },
          {
            path: "leads",
            element: <Leads />,
            loader: leadsLoader(context),
          },
          {
            path: "templates",
            element: <AllTemplates />,
            loader: templateMessagesLoader(context),
          },
          {
            path: "templates/create",
            element: <CreateOrEditTemplateMessage />,
            loader: createOrEditTemplateLoader(context),
            action: createOrEditTemplateAction(context),
          },
          {
            path: "templates/edit/:id",
            element: <CreateOrEditTemplateMessage />,
            loader: createOrEditTemplateLoader(context),
            action: createOrEditTemplateAction(context),
          },
          {
            path: "leads/create",
            element: <EnterLeadInfo />,
            loader: enterLeadInfoLoader,
            action: enterLeadAction(context),
            errorElement: <EnterLeadInfo />,
          },
          {
            path: "leads/create/success",
            element: <EnteredLeadSuccess />,
            loader: enteredLeadSuccessLoader,
          },
          {
            path: "lead-research-reports/:id",
            element: <LeadResearchReport />,
            loader: leadResearchReportLoader(context),
          },
        ],
      },
    ]);
  return <RouterProvider router={router(authContext)} />;
}

enableMocking().then(() => {
  const root = ReactDOM.createRoot(document.getElementById("root"));
  root.render(
    <React.StrictMode>
      <PostHogProvider
        apiKey={process.env.REACT_APP_PUBLIC_POSTHOG_KEY}
        options={postHogOptions}
      >
        <Root>
          <AppRoutes />
        </Root>
      </PostHogProvider>
    </React.StrictMode>
  );

  // If you want to start measuring performance in your app, pass a function
  // to log results (for example: reportWebVitals(console.log))
  // or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
  reportWebVitals();
});
