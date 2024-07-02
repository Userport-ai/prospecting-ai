import "./fetched-leads.css";
import { Typography, Button } from "antd";
import LeadsTable from "./leads-table";
import { useNavigate } from "react-router-dom";

const { Title } = Typography;

function FetchedLeads() {
  const navigate = useNavigate();
  return (
    <div id="fetched-leads-outer">
      <div id="fetched-leads-container">
        <Title level={3}>Leads</Title>
        <LeadsTable />
        <div id="add-leads-btn-container">
          <Button type="primary" onClick={() => navigate("/enter-lead-info")}>
            Add new lead
          </Button>
        </div>
      </div>
    </div>
  );
}

export default FetchedLeads;
