import "./leads.css";
import { Typography, Button, Spin } from "antd";
import LeadsTable from "./leads-table";
import {
  emptyLeadsResult,
  leadsInProgressResult,
  leadsResult,
} from "./leads-table-data";
import { useNavigate, useLoaderData, useNavigation } from "react-router-dom";
import { useContext, useEffect, useState } from "react";
import { AuthContext } from "./root";

const { Title } = Typography;

// Helper to fetch list of leads created by this user.
// TODO: Implement pagination.
async function fetch_leads(user) {
  const response = await fetch("/api/v1/leads", {
    headers: { Authorization: "Bearer " + user.accessToken },
  });
  const result = await response.json();
  // const result = await emptyLeadsResult;
  // const result = await leadsResult;
  // const result = await leadsInProgressResult;
  if (result.status === "error") {
    throw result;
  }
  return result.leads;
}

// Loader to fetch leads before component mounts.
export const leadsLoader = (authContext) => {
  return async () => {
    const { user } = authContext;
    if (!user) {
      // User is logged out.
      return null;
    }
    return fetch_leads(user);
  };
};

// Fetch and display leads.
// TODO: Implement pagination.
function Leads() {
  const { user } = useContext(AuthContext);
  const navigate = useNavigate();
  const gotLeads = useLoaderData();
  const [leads, setLeads] = useState(gotLeads);

  const navigation = useNavigation();
  const loading_or_submitting = navigation.state !== "idle";
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

  return (
    <div id="leads-outer">
      <div id="leads-container">
        <Title level={3}>Leads</Title>
        <LeadsTable leads={leads} />
        <div id="add-leads-btn-container">
          <Button type="primary" onClick={() => navigate("/enter-lead-info")}>
            Add new lead
          </Button>
        </div>
        <Spin spinning={loading_or_submitting} />;
      </div>
    </div>
  );
}

export default Leads;
