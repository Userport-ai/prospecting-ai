import "./leads.css";
import { Typography, Button, Spin } from "antd";
import LeadsTable from "./leads-table";
import { leadsResult } from "./leads-table";
import { useNavigate, useLoaderData, useNavigation } from "react-router-dom";

const { Title } = Typography;

// Loader to fetch leads.
export const leadsLoader = (authContext) => {
  return async () => {
    const { user } = authContext;
    if (!user) {
      // User is logged out.
      // return redirect("/login");
      return null;
    }
    const response = await fetch("/api/v1/leads");
    const result = await response.json();
    // const result = await leadsResult;
    if (result.status === "error") {
      throw result;
    }
    return result;
  };
};

function Leads() {
  const navigate = useNavigate();
  const leadsResult = useLoaderData();
  const navigation = useNavigation();
  const loading_or_submitting = navigation.state !== "idle";

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
        <Spin spinning={loading_or_submitting} />;
      </div>
    </div>
  );
}

export default Leads;
