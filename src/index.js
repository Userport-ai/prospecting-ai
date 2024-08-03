import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import AllTemplates from "./all-templates";
import { templateMessagesLoader } from "./all-templates";
import CreateTemplateMessage from "./create-template-message";
import { createTemplateAction } from "./create-template-message";
import FetchedLeads from "./fetched-leads";
import EnterLeadInfo from "./enter-lead-info";
import { enterLeadAction } from "./enter-lead-info";
import LeadResearchReport from "./lead-research-report";
import { leadResearchReportLoader } from "./lead-research-report";
import ErrorPage from "./error-page";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import reportWebVitals from "./reportWebVitals";
import "bootstrap/dist/css/bootstrap.css";
// Put any other imports below so that CSS from your
// components takes precedence over default styles.
import "./index.css";

const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    errorElement: <ErrorPage />,
    children: [
      {
        path: "/templates",
        element: <AllTemplates />,
        loader: templateMessagesLoader,
      },
      {
        path: "/create-template",
        element: <CreateTemplateMessage />,
        action: createTemplateAction,
      },
      {
        // Navigate home to leads page by default
        path: "/",
        element: <FetchedLeads />,
      },
      {
        path: "/leads",
        element: <FetchedLeads />,
      },
      {
        path: "/enter-lead-info",
        element: <EnterLeadInfo />,
        action: enterLeadAction,
        errorElement: <EnterLeadInfo />,
      },
      {
        path: "/lead-research-reports/:id",
        element: <LeadResearchReport />,
        loader: leadResearchReportLoader,
      },
    ],
  },
]);

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
