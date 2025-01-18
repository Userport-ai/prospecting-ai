import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarProvider,
  useSidebar,
} from "@/components/ui/sidebar";
import { Account as AccountRow } from "@/services/Accounts";
import { Lead as LeadRow } from "@/services/Leads";
import { CellContext, flexRender } from "@tanstack/react-table";
import { X } from "lucide-react";
import { getCustomColumnDisplayName } from "./AddCustomColumn";

// Need this interface to fix compilation error.
// Solution found here: https://github.com/shadcn-ui/ui/issues/5509
interface CustomCSSProperties extends React.CSSProperties {
  "--sidebar-width"?: string;
}

export type AccountOrLeadRow = AccountRow | LeadRow;

const CellSidebar: React.FC<{
  cellContext: CellContext<any, unknown>;
}> = ({ cellContext }) => {
  const { setOpen } = useSidebar();

  // Returns either company name or lead name.
  const getName = (row: AccountOrLeadRow) => {
    if ("name" in row) {
      // AccountRow object.
      const accountRow = row as AccountRow;
      return accountRow.name;
    } else {
      // LeadRow object.
      const leadRow = row as LeadRow;
      return `${leadRow.first_name} ${leadRow.last_name}`;
    }
  };

  // Returns LinkedIn URL from the given row.
  const getLinkedInURL = (row: AccountOrLeadRow): string => {
    return row.linkedin_url ? row.linkedin_url : "";
  };

  const row = cellContext.row.original as AccountOrLeadRow;

  return (
    <Sidebar
      side="right"
      variant="floating"
      className="bg-gray-50 shadow-xl rounded-l-lg border-l border-gray-200 p-0"
    >
      <SidebarHeader className="px-4 py-4 border-b border-gray-300 bg-gray-100 mb-4">
        <div className="flex justify-between">
          <div className="flex flex-col gap-2">
            <h1 className="text-xl text-gray-800 font-medium">
              {getName(row)}
            </h1>
            <a
              href={getLinkedInURL(row)}
              className="text-blue-500"
              target="_blank"
            >
              {getLinkedInURL(row)}
            </a>
          </div>
          <X
            className="text-gray-700 hover:cursor-pointer"
            onClick={() => setOpen(false)}
          />
        </div>
      </SidebarHeader>

      <SidebarContent className="px-6 py-4">
        <h2 className="text-lg font-medium text-gray-600">
          {getCustomColumnDisplayName(cellContext.column.id)}
        </h2>
        <div className="p-4 border border-gray-300 rounded-xl shadow-sm bg-gray-50">
          {flexRender(cellContext.cell.column.columnDef.cell, cellContext)}
        </div>
      </SidebarContent>
    </Sidebar>
  );
};

interface CellExpansionSidebarProps {
  cellContext: CellContext<any, unknown> | null;
  onOpenChange: (open: boolean) => void;
}

// Sidebar that displays detailed information of a Cell in a Table.
const CellExpansionSidebar: React.FC<CellExpansionSidebarProps> = ({
  cellContext,
  onOpenChange,
}) => {
  return (
    <SidebarProvider
      open={cellContext !== null}
      onOpenChange={onOpenChange}
      style={{ "--sidebar-width": "30rem" } as CustomCSSProperties}
    >
      {cellContext && <CellSidebar cellContext={cellContext} />}
    </SidebarProvider>
  );
};

export default CellExpansionSidebar;
