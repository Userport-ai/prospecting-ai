import React, { useContext } from "react";
import ReactDOM from "react-dom/client";
import Root, { AuthContext } from "./root";
import App from "./App";
import Login, { loginLoader } from "./login";
import AllTemplates from "./all-templates";
import { templateMessagesLoader } from "./all-templates";
import CreateOrEditTemplateMessage, {
  createOrEditTemplateLoader,
} from "./create-template-message";
import { createOrEditTemplateAction } from "./create-template-message";
import Leads from "./leads";
import { leadsLoader } from "./leads";
import EnterLeadInfo from "./enter-lead-info";
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
import "bootstrap/dist/css/bootstrap.css";
// Put any other imports below so that CSS from your
// components takes precedence over default styles.
import "./index.css";

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
        loader: loginLoader(context),
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
            action: enterLeadAction(context),
            errorElement: <EnterLeadInfo />,
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

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <Root>
      <AppRoutes />
    </Root>
  </React.StrictMode>
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
