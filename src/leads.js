import "./leads.css";
import { Typography, Button } from "antd";
import LeadsTable from "./leads-table";
import { leadsResult } from "./leads-table";
import { useNavigate, useLoaderData } from "react-router-dom";

const { Title } = Typography;

// Loader to fetch leads.
export async function leadsLoader() {
  // const response = await fetch("/api/v1/leads");
  // const result = await response.json();
  const result = await leadsResult;
  if (result.status === "error") {
    throw result;
  }
  return result;
}

function Leads() {
  const navigate = useNavigate();
  const leadsResult = useLoaderData();

  return (
    <div id="leads-outer">
      <div id="leads-container">
        <Title level={3}>Leads</Title>
        <LeadsTable leads={leadsResult.leads} />
        <div id="add-leads-btn-container">
          <Button type="primary" onClick={() => navigate("/enter-lead-info")}>
            Add new lead
          </Button>
        </div>
      </div>
    </div>
  );
}

export default Leads;
