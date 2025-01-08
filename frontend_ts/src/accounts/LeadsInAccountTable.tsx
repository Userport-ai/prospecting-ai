import LeadsTable from "@/leads/LeadsTable";

// Wrapper component around Leads Table so that
// Client side routing can differentiate
// between /accounts/:id/leads and /leads and reload
// the LeadsTable component when navigating from
// one to the other.
const LeadsInAccountTable = () => {
  return <LeadsTable />;
};

export default LeadsInAccountTable;
