import "./fetched-leads.css";
import { Typography, Button } from "antd";
import LeadsTable from "./leads-table";

const { Title } = Typography;

function FetchedLeads() {
  return (
    <div id="fetched-leads-outer">
      <div id="fetched-leads-container">
        <Title level={3}>Leads</Title>
        <LeadsTable />
        <div id="add-leads-btn-container">
          <Button type="primary">Add new lead</Button>
        </div>
      </div>
    </div>
  );
}

export default FetchedLeads;
