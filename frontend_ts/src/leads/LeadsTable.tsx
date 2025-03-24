import { useEffect, useState } from "react";
import {
  getCoreRowModel,
  useReactTable,
  getSortedRowModel,
  getFilteredRowModel,
  ColumnDef,
  ColumnSort,
} from "@tanstack/react-table";
import AddCustomColumn, {
  getCustomColumnDisplayName,
} from "@/table/AddCustomColumn";
import { CustomColumnInput } from "@/table/AddCustomColumn";
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
import { Download } from "lucide-react";
import { exportToCSV } from "@/common/utils";

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
  onCustomColumnAdded: (arg0: CustomColumnInput) => void;
  onPageSizeChange: (pageSize: number) => void;
  allPersonaFilterValues: string[];
  personaFilterValues: string[];
  onPersonaFilterValuesChange: (newPersonaFilterValues: string[]) => void;
}

export const Table: React.FC<TableProps> = ({
  columns,
  leads,
  totalLeadsCount,
  curPageNum,
  curPageSize,
  handlePageClick,
  dataLoading,
  onCustomColumnAdded,
  onPageSizeChange,
  allPersonaFilterValues,
  personaFilterValues,
  onPersonaFilterValuesChange,
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

  const handleCustomColumnAdd = (customColumnInfo: CustomColumnInput) => {
    // Fetch the rows that need to be enriched. By default,
    // we fetch all the rows on the current page.
    const rowIds = table.getRowModel().rows.map((row) => row.original.id);
    customColumnInfo.rowIds = rowIds;
    onCustomColumnAdded(customColumnInfo);
  };

  // Handler to export selected leads to CSV.
  const exportSelectedLeadsToCSV = () => {
    // Transform selected leads before export.
    const transformedLeads = selectedLeads.map((lead: LeadRow) => {
      return {
        Name: lead.first_name + " " + lead.last_name,
        "LinkedIn URL": lead.linkedin_url,
        "Company Name": lead.account_details.name,
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
          : "unknown",
        "Matching Signals":
          lead.custom_fields && lead.custom_fields.evaluation.matching_signals
            ? lead.custom_fields.evaluation.matching_signals.join("\n\n")
            : "unknown",
      };
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
      <div className="sticky top-0 z-50 border border-gray-200 shadow-md bg-white p-2 flex gap-6">
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
        <AddCustomColumn onAdded={handleCustomColumnAdd} />

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
  const [personaFilterValues, setPersonaFilterValues] = useState<string[]>(
    allPersonaFilterValues
  );

  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [dataLoading, setDataLoading] = useState<boolean>(false);

  const listLeads = async (cursor: string | null) => {
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
    setColumns(getLeadColumns(response.results));
    return response;
  };

  // Initial fetch for leads.
  useEffect(() => {
    setLoading(true);
    listLeads(null)
      .then((response) => {
        setCurPageNum(1);
        setCursorValues([null, response.next_cursor ?? null]);
      })
      .catch((error) =>
        setError(new Error(`Failed to fetch Leads: ${error.message}`))
      )
      .finally(() => setLoading(false));
  }, [authContext, curPageSize, personaFilterValues]);

  if (loading) {
    return <ScreenLoader />;
  }

  if (error) {
    throw error;
  }

  // Handler for when custom column inputs are provided by the user.
  const onCustomColumnAdded = (customColumnInfo: CustomColumnInput) => {
    // TODO: call server to send custom column request instead.
    console.log("custom colum info: ", customColumnInfo);
  };

  // Handle user request to go to page.
  // If goToNextPage is true, fetch next page, otherwise fetch previous page.
  // We assume this callback can be called only if next or prev page buttons
  // are enabled in the UI. In other words, we assume those validations are already done.
  const handlePageClick = async (goToNextPage: boolean) => {
    setDataLoading(true);
    const nextPageNum = goToNextPage ? curPageNum + 1 : curPageNum - 1;
    const cursor = cursorValues[nextPageNum - 1];
    try {
      const response = await listLeads(cursor);
      setCurPageNum(nextPageNum);
      // We assume that user can only go forward or back one page at a time.
      // TODO: If we allow user to go page X directly, then this logic has to be updated.
      if (goToNextPage) {
        // Append next cursor value.
        setCursorValues([...cursorValues, response.next_cursor ?? null]);
      } else {
        // Remove cursor values whose index values are larger than next page num.
        setCursorValues(cursorValues.filter((_, idx) => idx <= nextPageNum));
      }
    } catch (error: any) {
      setError(
        new Error(
          `Failed to fetch Leads nextPage: ${goToNextPage} with next page num: ${nextPageNum} cursor: ${cursor} with error: ${error.message}`
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

  return (
    <Table
      columns={columns}
      leads={curLeads}
      totalLeadsCount={totalLeadsCount}
      curPageNum={curPageNum}
      curPageSize={curPageSize}
      handlePageClick={handlePageClick}
      dataLoading={dataLoading}
      onCustomColumnAdded={onCustomColumnAdded}
      onPageSizeChange={setCurPageSize}
      allPersonaFilterValues={allPersonaFilterValues}
      personaFilterValues={personaFilterValues}
      onPersonaFilterValuesChange={onPersonaFilterValuesChange}
    />
  );
};

export default LeadsTable;
