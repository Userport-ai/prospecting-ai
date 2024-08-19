import "./leads.css";
import { Button, Skeleton } from "antd";
import LeadsTable from "./leads-table";
import {
  emptyLeadsResult,
  leadsInProgressResult,
  leadsResult,
} from "./leads-table-data";
import {
  useNavigate,
  useLoaderData,
  useNavigation,
  redirect,
} from "react-router-dom";
import { useContext, useEffect, useState } from "react";
import { AuthContext } from "./root";

// Helper to fetch list of leads created by this user.
// TODO: Implement pagination.
async function fetch_leads(user) {
  // Get Id token using Firebase API instead of accessing token directly per: https://stackoverflow.com/questions/47803495/error-firebase-id-token-has-expired.
  const idToken = await user.getIdToken();
  const response = await fetch("/api/v1/leads", {
    headers: { Authorization: "Bearer " + idToken },
  });
  const result = await response.json();
  // const result = await emptyLeadsResult;
  // const result = await leadsResult;
  // const result = await leadsInProgressResult;
  if (result.status === "error") {
    throw result;
  }
  const userState = result.user.state;
  if (userState === "new_user") {
    // If new user, redirect to /templates so they can first create a template.
    return redirect("/templates");
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
    // If user email is not verified, redirect.
    if (!user.emailVerified) {
      return redirect("/verify-email");
    }
    return fetch_leads(user);
  };
};

// Fetch and display leads.
// TODO: Implement pagination.
function Leads() {
  const { user } = useContext(AuthContext);
  const navigate = useNavigate();
  const gotLeadsResponse = useLoaderData();
  const [leads, setLeads] = useState(gotLeadsResponse.leads);

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
      const leads = await fetch_leads(user);
      setLeads(leads);
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

  return (
    <div id="leads-outer">
      <div id="leads-container">
        <div id="title-and-btn-container">
          <h1>Leads</h1>
          <Button type="primary" onClick={() => navigate("/leads/create")}>
            Add new lead
          </Button>
        </div>
        <LeadsTable leads={leads} />
      </div>
    </div>
  );
}

export default Leads;
