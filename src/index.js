import React, { useContext } from "react";
import ReactDOM from "react-dom/client";
import Root, { AuthContext } from "./root";
import App from "./App";
import Login from "./login";
import AllTemplates from "./all-templates";
import { templateMessagesLoader } from "./all-templates";
import CreateTemplateMessage from "./create-template-message";
import { createTemplateAction } from "./create-template-message";
import Leads from "./leads";
import { leadsLoader } from "./leads";
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
import { auth } from "firebaseui";

function AppRoutes() {
  const authContext = useContext(AuthContext);
  const router = (context) =>
    createBrowserRouter([
      {
        path: "/login",
        element: <Login />,
      },
      {
        path: "/",
        element: <App />,
        errorElement: <ErrorPage />,
        children: [
          {
            path: "templates",
            element: <AllTemplates />,
            loader: templateMessagesLoader(context),
          },
          {
            path: "create-template",
            element: <CreateTemplateMessage />,
            action: createTemplateAction,
          },
          {
            path: "leads",
            element: <Leads />,
            loader: leadsLoader(context),
          },
          {
            path: "enter-lead-info",
            element: <EnterLeadInfo />,
            action: enterLeadAction,
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
