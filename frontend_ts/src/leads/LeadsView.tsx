import { Separator } from "@/components/ui/separator";
import LeadsTable from "./LeadsTable";

// Component that displays Leads page view in a given account.
const LeadsView = () => {
  return (
    <div className="mx-auto px-4 py-2">
      <h1 className="font-bold text-gray-700 text-2xl">All Leads</h1>
      <Separator className="my-4 bg-gray-300" />
      <LeadsTable />
    </div>
  );
};

export default LeadsView;
