import "./leads.css";
import { Button, Skeleton } from "antd";
import LeadsTable from "./leads-table";
import { useNavigate, useLoaderData, useNavigation } from "react-router-dom";
import { useContext, useEffect, useState } from "react";
import { AuthContext } from "./root";
import {
  isUserOnboarding,
  userHasNotCreatedLead,
  userHasNotCreatedTemplate,
} from "./helper-functions";
import OnboardingProgressBar from "./onboarding-progress-bar";
import { usePostHog } from "posthog-js/react";

// Helper to fetch list of leads created by this user.
// TODO: Implement pagination.
async function listLeads(user) {
  // Get Id token using Firebase API instead of accessing token directly per: https://stackoverflow.com/questions/47803495/error-firebase-id-token-has-expired.
  const idToken = await user.getIdToken();
  const response = await fetch("/api/v1/leads", {
    headers: { Authorization: "Bearer " + idToken },
  });
  const result = await response.json();
  if (result.status === "error") {
    throw result;
  }
  return result;
}

// Loader to fetch leads before component mounts.
export const leadsLoader = (authContext) => {
  return async () => {
    const { user } = authContext;
    if (!user) {
      // User is logged out.
      return null;
    }
    const result = await listLeads(user);
    return result;
  };
};

// Fetch and display leads.
// TODO: Implement pagination.
function Leads() {
  const { user } = useContext(AuthContext);
  const navigate = useNavigate();
  const loaderResponse = useLoaderData();
  const userFromServer = loaderResponse.user;
  const [leads, setLeads] = useState(loaderResponse.leads);
  const posthog = usePostHog();

  const component_is_loading = useNavigation().state !== "idle";
  const should_poll_periodically = leads.some(
    (lead) => !["complete", "failed_with_errors"].includes(lead.status)
  );
  const POLLING_INTERVAL = 60 * 1000; // Poll every 1 min.

  // Setup polling.
  useEffect(() => {
    if (!should_poll_periodically) {
      // Do nothing.
      return;
    }

    const intervalId = setInterval(async () => {
      const result = await listLeads(user);
      setLeads(result.leads);
    }, POLLING_INTERVAL);
    return () => clearInterval(intervalId);
  }, [should_poll_periodically, user, POLLING_INTERVAL]);

  if (!user) {
    // User not logged in, return.
    return null;
  }
  if (component_is_loading) {
    return (
      <Skeleton
        active
        paragraph={{
          rows: 15,
        }}
      />
    );
  }

  // Handle Add Lead button click by user.
  function handleAddLeadClick() {
    // Send event.
    posthog.capture("add_lead_btn_clicked");
    // TODO: Let's see if we should remove this completely.
    // if (userHasNotCreatedTemplate(userFromServer.state)) {
    //   // Prompt the user that they need to create a template first.
    //   Modal.error({
    //     title: "Template not created yet",
    //     content: "Please create template for the persona first.",
    //   });
    //   return;
    // }

    var nextPage = "/leads/create";
    if (userHasNotCreatedLead(userFromServer.state)) {
      // Pass this information about the user in the URL path.
      const urlParams = new URLSearchParams({
        state: userFromServer.state,
      }).toString();
      nextPage += `?${urlParams}`;
    }
    return navigate(nextPage);
  }

  return (
    <div id="leads-outer">
      {isUserOnboarding(userFromServer) && (
        <OnboardingProgressBar userFromServer={userFromServer} />
      )}
      <div id="leads-container">
        <div id="title-and-btn-container">
          <h1>Leads</h1>
          <Button type="primary" onClick={handleAddLeadClick}>
            Add new lead
          </Button>
        </div>
        <LeadsTable leads={leads} />
      </div>
    </div>
  );
}

export default Leads;
