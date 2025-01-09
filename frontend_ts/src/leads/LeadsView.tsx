import LeadsTable from "./LeadsTable";

// Component that displays Leads page view in a given account.
const LeadsView = () => {
  return (
    <div className="w-11/12 mx-auto py-2">
      <h1 className="font-bold text-gray-700 text-2xl mb-5">All Leads</h1>
      <LeadsTable />
    </div>
  );
};

export default LeadsView;
