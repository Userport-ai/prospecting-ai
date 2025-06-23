import { useEffect, useState } from "react";
import {
  getCoreRowModel,
  useReactTable,
  getSortedRowModel,
  getFilteredRowModel,
  ColumnDef,
  ColumnSort,
} from "@tanstack/react-table";
import { getCustomColumnDisplayName } from "@/table/AddCustomColumn";
import CommonTable from "@/table/CommonTable";
import TextFilter from "@/table/TextFilter";
import { getLeadColumns } from "./Columns";
import { CustomColumnMeta } from "@/table/CustomColumnMeta";
import { Lead as LeadRow, listLeadsWithQuota } from "@/services/Leads";
import { useAuthContext } from "@/auth/AuthProvider";
import ScreenLoader from "@/common/ScreenLoader";
import LoadingOverlay from "@/common/LoadingOverlay";
import EnumFilterV2 from "@/table/EnumFilterV2";
import { Button } from "@/components/ui/button";
import { Cpu, Download, Loader2 } from "lucide-react";
import { exportToCSV } from "@/common/utils";
import CreateOrEditCustomColumnDialog, {
  EntityType,
} from "@/components/custom-columns/CustomColumnDialog";
import { CustomColumn } from "@/services/CustomColumn";

interface BaseLeadInfoForCSVExport {
  Name: string;
  "LinkedIn URL"?: string;
  "Company Name"?: string;
  "Company Website"?: string;
  "Role Title": string | null;
  "Fit Score": number | null;
  "Persona Match": string;
  Rationale: string[];
  "Matching Signals": string;
  "Recent Company Highlights": string;
  [key: string]: any; // Allows dynamic addition of string keys with any value type
}

const ZeroStateDisplay = () => {
  return (
    <div className="flex flex-col gap-2 items-center justify-center h-64 text-center bg-gray-50 border border-dashed border-gray-300 rounded-md p-6">
      <div className="text-gray-600 mb-4">
        <div className="text-xl font-semibold">No Data Available</div>
        <div className="text-sm">Start by adding Accounts to prospect.</div>
      </div>
    </div>
  );
};

interface TableProps {
  columns: ColumnDef<LeadRow>[];
  leads: LeadRow[];
  totalLeadsCount: number;
  curPageNum: number;
  curPageSize: number;
  handlePageClick: (goToNextPage: boolean) => Promise<void>;
  dataLoading: boolean;
  onPageSizeChange: (pageSize: number) => void;
  allPersonaFilterValues: string[];
  personaFilterValues: string[];
  onPersonaFilterValuesChange: (newPersonaFilterValues: string[]) => void;
  customColumnDialogOpen: boolean;
  onCustomColumnDialogOpenChange: (open: boolean) => void;
  onColumnCreated: (newColumn: CustomColumn) => Promise<void>;
  editCustomColumn: CustomColumn | null;
}

export const Table: React.FC<TableProps> = ({
  columns,
  leads,
  totalLeadsCount,
  curPageNum,
  curPageSize,
  handlePageClick,
  dataLoading,
  onPageSizeChange,
  allPersonaFilterValues,
  personaFilterValues,
  onPersonaFilterValuesChange,
  customColumnDialogOpen,
  onCustomColumnDialogOpenChange,
  onColumnCreated,
  editCustomColumn,
}) => {
  const [sorting, setSorting] = useState<ColumnSort[]>([]);
  // This is only a JSON object mapping selected Row ID to true.
  const [rowSelection, setRowSelection] = useState<Record<string, boolean>>({});
  const pageCount = Math.ceil(totalLeadsCount / curPageSize);

  // Create list of selected leads.
  var leadMap: Record<string, LeadRow> = {};
  for (const l of leads) {
    leadMap[l.id] = l;
  }
  const selectedLeads: LeadRow[] = Object.keys(rowSelection).map(
    (id) => leadMap[id]
  );

  var initialColumnVisibility: Record<string, boolean> = {};
  columns.forEach((col) => {
    if (!col.id) {
      return;
    }
    initialColumnVisibility[col.id] = false;
    if ((col.meta as CustomColumnMeta).visibleInitially === true) {
      initialColumnVisibility[col.id] = true;
    }
  });
  const [columnVisibility, setColumnVisibility] = useState(
    initialColumnVisibility
  );
  // Following https://tanstack.com/table/v8/docs/framework/react/examples/column-sizing for column resizing
  const columnResizeMode = "onChange";
  const columnResizeDirection = "ltr";

  const table = useReactTable({
    data: leads,
    columns,
    columnResizeMode,
    columnResizeDirection,
    getCoreRowModel: getCoreRowModel(),
    pageCount: pageCount,
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    onSortingChange: setSorting,
    onColumnVisibilityChange: setColumnVisibility,
    onRowSelectionChange: setRowSelection,
    getRowId: (row) => row.id, //use the lead's ID
    // Needed to solve this error: https://github.com/TanStack/table/issues/5026.
    autoResetPageIndex: false,
    state: {
      sorting,
      columnVisibility,
      rowSelection,
    },
  });

  if (leads.length === 0) {
    // No accounts found.
    return <ZeroStateDisplay />;
  }

  // Handler to export selected leads to CSV.
  const exportSelectedLeadsToCSV = () => {
    // Transform selected leads before export.
    const transformedLeads = selectedLeads.map((lead: LeadRow) => {
      var baseLeadInfo: BaseLeadInfoForCSVExport = {
        Name: lead.first_name + " " + lead.last_name,
        "LinkedIn URL": lead.linkedin_url,
        "Company Name": lead.account_details.name,
        "Company Website": lead.account_details.website,
        "Role Title": lead.role_title,
        "Fit Score": lead.score,
        "Persona Match":
          lead.custom_fields &&
          lead.custom_fields.evaluation &&
          lead.custom_fields.evaluation.persona_match &&
          lead.custom_fields.evaluation.persona_match !== "null"
            ? lead.custom_fields.evaluation.persona_match
            : "unknown",
        Rationale: lead.custom_fields
          ? lead.custom_fields.evaluation.rationale
          : [],
        "Matching Signals":
          lead.custom_fields && lead.custom_fields.evaluation.matching_signals
            ? lead.custom_fields.evaluation.matching_signals.join("\n\n")
            : "unknown",
        "Recent Company Highlights": lead.account_details.recent_events
          ? lead.account_details.recent_events
              .map((evt) => `${evt.description}\n${evt.date}`)
              .join("\n\n")
          : "none",
      };

      // Add custom columns if any.
      if (lead.custom_column_values) {
        for (const columnId in lead.custom_column_values) {
          const colData = lead.custom_column_values[columnId];
          baseLeadInfo[colData.name] = colData.value;
        }
      }
      return baseLeadInfo;
    });
    exportToCSV(transformedLeads, "userport-leads");
  };

  return (
    <div className="flex flex-col gap-4">
      <p className="text-gray-700 text-md mb-2">
        Total Number of Leads:{" "}
        <span className="font-semibold">{totalLeadsCount}</span>
      </p>

      {/* Floating Toolbar */}
      <div className="sticky top-0 z-10 border border-gray-200 shadow-md bg-white p-2 flex gap-6">
        {/* Filter Controls */}
        <div className="flex gap-4">
          <TextFilter
            table={table}
            columnId={"name"}
            placeholder={"Filter Lead name..."}
          />

          <EnumFilterV2
            displayName={getCustomColumnDisplayName("persona_match")}
            allFilterValues={allPersonaFilterValues}
            initialFilterValues={personaFilterValues}
            onFilterValuesChanged={onPersonaFilterValuesChange}
          />
        </div>

        {/* Add custom column */}
        <Button
          onClick={() => onCustomColumnDialogOpenChange(true)}
          variant="outline"
          className="flex gap-2 items-center px-4 py-2 text-sm font-medium text-gray-600 rounded-md shadow-sm bg-white hover:bg-gray-100 transition duration-300 border-gray-200"
        >
          <Cpu size={16} /> Ask AI
        </Button>

        <CreateOrEditCustomColumnDialog
          customColumn={editCustomColumn}
          entityType={EntityType.LEAD}
          open={customColumnDialogOpen}
          onOpenChange={onCustomColumnDialogOpenChange}
          onSuccess={onColumnCreated}
        />

        {/* Floating Action Bar */}
        {selectedLeads.length > 0 && (
          <div className="flex gap-4 px-2 items-center">
            <p className="text-sm text-gray-700">
              {selectedLeads.length} selected
            </p>
            <Button
              className="border border-gray-300 bg-white"
              onClick={exportSelectedLeadsToCSV}
              variant="outline"
            >
              <Download /> Export
            </Button>
          </div>
        )}
      </div>

      {/* Table Container */}
      <CommonTable
        table={table}
        columns={columns}
        columnResizeMode={columnResizeMode}
        curPageNum={curPageNum}
        totalPageCount={pageCount}
        handlePageClick={handlePageClick}
        headerClassName="bg-[rgb(180,150,200)]"
        curPageSize={curPageSize}
        onPageSizeChange={onPageSizeChange}
      />

      <LoadingOverlay loading={dataLoading} />
    </div>
  );
};

interface LeadsTableProps {
  // Account ID not present when we want to
  // list across all accounts.
  accountId?: string;
}

// Displays table with list of leads.
const LeadsTable: React.FC<LeadsTableProps> = ({ accountId }) => {
  const authContext = useAuthContext();
  // Current list of all leads fetched from server so far in the correct pagination order.
  const [curLeads, setCurLeads] = useState<LeadRow[]>([]);
  // Current Page number (fetched from server). Valid page numbers start from 1.
  const [curPageNum, setCurPageNum] = useState<number>(0);
  // Current page size.
  const [curPageSize, setCurPageSize] = useState<number>(20);
  // Cursor values associated with the pages fetched from server.
  // Initially null since page 1 always has null cursor value.
  const [cursorValues, setCursorValues] = useState<(string | null)[]>([null]);
  // Total leads count found on the server.
  const [totalLeadsCount, setTotalLeadsCount] = useState(0);
  const [columns, setColumns] = useState<ColumnDef<LeadRow>[]>([]);
  // Filters used for Persona Match.
  const allPersonaFilterValues = ["buyer", "influencer", "end_user", "unknown"];
  const initialPersonaFilterValues = ["buyer", "influencer"];
  const [personaFilterValues, setPersonaFilterValues] = useState<string[]>(
    initialPersonaFilterValues
  );

  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [dataLoading, setDataLoading] = useState<boolean>(false);
  const [customColumnDialogOpen, setCustomColumnDialogOpen] = useState(false);
  const [backgroundRefreshing, setBackgroundRefreshing] = useState(false);
  const [tableNeedRefresh, setTableNeedsRefresh] = useState(false);
  const [editCustomColumn, setEditCustomColumn] = useState<CustomColumn | null>(
    null
  );

  // Function to refresh table data (leads) in the background without full loading overlay
  const refreshTableData = () => {
    setTableNeedsRefresh(true);
  };

  // List leads
  useEffect(() => {
    if (!tableNeedRefresh) {
      return;
    }

    const pollLeads = async () => {
      try {
        const response = await listLeads(cursorValues[curPageNum - 1], false);
        const pollingRequired = response.results.some((lead) => {
          const customColumnValuesMap = lead.custom_column_values;
          if (!customColumnValuesMap) {
            return false;
          }
          return Object.keys(customColumnValuesMap).some(
            (columnId) =>
              customColumnValuesMap[columnId].status &&
              (customColumnValuesMap[columnId].status === "pending" ||
                customColumnValuesMap[columnId].status === "processing")
          );
        });

        if (!pollingRequired) {
          // No need to poll.
          console.log("nothing to poll for leads");
          setTableNeedsRefresh(false);
          return;
        }

        console.log("polling leads.");
      } catch (error) {
        console.error("Failed to refresh Leads table:", error);
        // Optionally show a toast notification instead of setting error state
        // toast.error(`Failed to refresh: ${error.message}`);
      }
    };

    // Call immediately once.
    pollLeads();

    const pollingInterval = 30 * 1000; // Poll every 30s.
    const intervalId = setInterval(pollLeads, pollingInterval);

    // Clean up the interval when the component unmounts
    return () => {
      console.log("Cleaning up lead polling interval: ", intervalId);
      clearInterval(intervalId);
    };
  }, [tableNeedRefresh]);

  // Improved listLeads function with better loading state handling
  const listLeads = async (
    cursor: string | null,
    showLoadingOverlay = true
  ) => {
    // Always use full loading overlay for initial data fetch (when curPageNum is 0)
    const useFullLoading = showLoadingOverlay;

    if (useFullLoading) {
      setDataLoading(true);
    } else {
      setBackgroundRefreshing(true);
    }

    try {
      const response = await listLeadsWithQuota(authContext, {
        accountId: accountId ?? null,
        cursor: cursor,
        limit: curPageSize,
        buyer_percent: 60,
        influencer_percent: 35,
        end_user_percent: 5,
        persona_filter_values: personaFilterValues,
      });

      setTotalLeadsCount(response.count);
      setCurLeads(response.results);
      setColumns(
        getLeadColumns(
          response.results,
          refreshTableData,
          onCustomColumnEditRequest
        )
      );

      return response;
    } catch (error: any) {
      console.error(`Failed to fetch Leads: ${error.message}`);
      throw error;
    } finally {
      if (useFullLoading) {
        setDataLoading(false);
      } else {
        setBackgroundRefreshing(false);
      }
    }
  };

  // Initial fetch for leads with improved loading
  useEffect(() => {
    setLoading(true);
    listLeads(null, false)
      .then((response) => {
        setCurPageNum(1);
        setCursorValues([null, response.next_cursor ?? null]);
      })
      .catch((error) =>
        setError(new Error(`Failed to fetch Leads: ${error.message}`))
      )
      .finally(() => setLoading(false));
  }, [authContext, curPageSize, personaFilterValues]);

  // Handle user request to go to page with improved loading
  const handlePageClick = async (goToNextPage: boolean) => {
    setDataLoading(true);
    const nextPageNum = goToNextPage ? curPageNum + 1 : curPageNum - 1;
    const cursor = cursorValues[nextPageNum - 1];

    try {
      const response = await listLeads(cursor, true);
      setCurPageNum(nextPageNum);

      // Update cursor values appropriately
      if (goToNextPage) {
        setCursorValues([...cursorValues, response.next_cursor ?? null]);
      } else {
        setCursorValues(cursorValues.filter((_, idx) => idx <= nextPageNum));
      }
    } catch (error: any) {
      setError(
        new Error(
          `Failed to fetch Leads for page ${nextPageNum}: ${error.message}`
        )
      );
    } finally {
      setDataLoading(false);
    }
  };

  // Handle change to persona filters.
  const onPersonaFilterValuesChange = (newPersonaFilterValues: string[]) => {
    const newPersonaFiltersSet = new Set(newPersonaFilterValues);
    const curPersonaFiltersSet = new Set(personaFilterValues);
    if (
      newPersonaFiltersSet.size == curPersonaFiltersSet.size &&
      [...newPersonaFiltersSet].every((filter) =>
        curPersonaFiltersSet.has(filter)
      )
    ) {
      // Filters have not changed.
      return;
    }
    // Filters have changed.
    setPersonaFilterValues(newPersonaFilterValues);
  };

  // Handle creation of new custom column.
  const handleColumnCreated = async (newColumn: CustomColumn) => {
    try {
      // Refetch the current page so that the created column is visible in the UI.
      await listLeads(cursorValues[curPageNum - 1], true);
    } catch (error) {
      setError(
        new Error(
          `Failed to fetch Leads after creating column ${newColumn} for page ${curPageNum}: ${error}`
        )
      );
    }
  };

  // Handler for when a custom column edit is requested by the user.
  const onCustomColumnEditRequest = (customColumn: CustomColumn) => {
    setEditCustomColumn(customColumn);
    setCustomColumnDialogOpen(true);
  };

  // Handle for when custom column dialog's open state changes
  const onCustomColumnDialogOpenChange = (open: boolean) => {
    if (!open) {
      setCustomColumnDialogOpen(false);
      setEditCustomColumn(null);
    } else {
      setCustomColumnDialogOpen(true);
    }
  };

  if (loading) {
    return <ScreenLoader />;
  }

  if (error) {
    throw error;
  }

  return (
    <div>
      {/* Subtle background refresh indicator */}
      {backgroundRefreshing && (
        <div className="text-xs text-gray-500 flex items-center mb-2">
          <Loader2 className="h-3 w-3 mr-1 animate-spin" />
          Refreshing data...
        </div>
      )}

      <Table
        columns={columns}
        leads={curLeads}
        totalLeadsCount={totalLeadsCount}
        curPageNum={curPageNum}
        curPageSize={curPageSize}
        handlePageClick={handlePageClick}
        dataLoading={dataLoading}
        onPageSizeChange={setCurPageSize}
        allPersonaFilterValues={allPersonaFilterValues}
        personaFilterValues={personaFilterValues}
        onPersonaFilterValuesChange={onPersonaFilterValuesChange}
        customColumnDialogOpen={customColumnDialogOpen}
        onCustomColumnDialogOpenChange={onCustomColumnDialogOpenChange}
        onColumnCreated={handleColumnCreated}
        editCustomColumn={editCustomColumn}
      />
    </div>
  );
};

export default LeadsTable;
