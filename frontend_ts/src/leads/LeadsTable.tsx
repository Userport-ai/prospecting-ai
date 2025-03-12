import { useEffect, useState } from "react";
import {
  getCoreRowModel,
  useReactTable,
  getSortedRowModel,
  getFilteredRowModel,
  ColumnDef,
  ColumnSort,
  ColumnFilter,
  ColumnFiltersState,
  Updater,
} from "@tanstack/react-table";
import AddCustomColumn from "@/table/AddCustomColumn";
import { CustomColumnInput } from "@/table/AddCustomColumn";
import CommonTable from "@/table/CommonTable";
import EnumFilter from "@/table/EnumFilter";
import TextFilter from "@/table/TextFilter";
import { getLeadColumns } from "./Columns";
import { CustomColumnMeta } from "@/table/CustomColumnMeta";
import { Lead as LeadRow, listLeadsWithQuota } from "@/services/Leads";
import { useAuthContext } from "@/auth/AuthProvider";
import ScreenLoader from "@/common/ScreenLoader";
import { USERPORT_TENANT_ID } from "@/services/Common";
import LoadingOverlay from "@/common/LoadingOverlay";

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
  handlePageClick: (goToNextPage: boolean) => Promise<void>;
  dataLoading: boolean;
  onCustomColumnAdded: (arg0: CustomColumnInput) => void;
}

export const Table: React.FC<TableProps> = ({
  columns,
  leads,
  totalLeadsCount,
  curPageNum,
  handlePageClick,
  dataLoading,
  onCustomColumnAdded,
}) => {
  const authContext = useAuthContext();
  const [sorting, setSorting] = useState<ColumnSort[]>([]);

  var persona_filter_values: string[] = [];
  if (authContext.userContext?.tenant.id !== USERPORT_TENANT_ID) {
    persona_filter_values = ["buyer", "influencer", "end_user", "null"];
  } else {
    // Test account, so we use only the two personas here.
    // TODO: Change once this is no longer the test account.
    persona_filter_values = ["buyer", "influencer"];
  }

  const [columnFilters, setColumnFilters] = useState<ColumnFilter[]>([
    {
      id: "persona_match",
      value: persona_filter_values,
    },
  ]);
  const [rowSelection, setRowSelection] = useState<Record<string, boolean>>({});

  const initialPaginationState = {
    pageIndex: 0, //initial page index
    pageSize: 20, //default page size
  };
  const [pagination, setPagination] = useState(initialPaginationState);
  const pageCount = Math.ceil(totalLeadsCount / pagination.pageSize);

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

  // When column filters page, we should reset pagination to state otherwise
  // table view gets messed up (page numbers are invalid).
  const onColumnFiltersChange = (
    newColumnFiltersState: Updater<ColumnFiltersState>
  ) => {
    // TODO call server to fetch new set of filters.
    // Reset page page index to initial page.
    setPagination(initialPaginationState);
    setColumnFilters(newColumnFiltersState);
  };

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
    onColumnFiltersChange: onColumnFiltersChange,
    onColumnVisibilityChange: setColumnVisibility,
    onRowSelectionChange: setRowSelection,
    getRowId: (row) => row.id, //use the lead's ID
    onPaginationChange: setPagination,
    // Needed to solve this error: https://github.com/TanStack/table/issues/5026.
    autoResetPageIndex: false,
    state: {
      sorting,
      columnFilters,
      columnVisibility,
      rowSelection,
      pagination,
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

  return (
    <div className="flex flex-col gap-4">
      <p className="text-gray-700 text-md mb-2">
        Total Number of Leads:{" "}
        <span className="font-semibold">{totalLeadsCount}</span>
      </p>
      <div className="flex gap-6">
        {/* Filter Controls */}
        <div className="flex gap-4">
          <TextFilter
            table={table}
            columnId={"name"}
            placeholder={"Filter Lead name..."}
          />

          {/* Status Filter */}
          <EnumFilter
            table={table}
            columnId={"persona_match"}
            columnFilters={columnFilters}
          />
        </div>

        {/* Add custom column */}
        <AddCustomColumn onAdded={handleCustomColumnAdd} />
      </div>

      {/* Table Container */}
      <CommonTable
        table={table}
        columns={columns}
        columnResizeMode={columnResizeMode}
        curPageNum={curPageNum}
        totalPageCount={pageCount}
        handlePageClick={handlePageClick}
        numSelectedRows={Object.keys(rowSelection).length}
        headerClassName="bg-[rgb(180,150,200)]"
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
  // Cursor values associated with the pages fetched from server.
  // Initially null since page 1 always has null cursor value.
  const [cursorValues, setCursorValues] = useState<(string | null)[]>([null]);
  // Total leads count found on the server.
  const [totalLeadsCount, setTotalLeadsCount] = useState(0);
  const [columns, setColumns] = useState<ColumnDef<LeadRow>[]>([]);

  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [dataLoading, setDataLoading] = useState<boolean>(false);

  const listLeads = async (cursor: string | null) => {
    const response = await listLeadsWithQuota(authContext, cursor, accountId);
    setTotalLeadsCount(response.count);
    setCurLeads(response.results);
    setColumns(getLeadColumns(response.results));
    return response;
  };

  // Initial fetch for leads.
  useEffect(() => {
    listLeads(cursorValues[0])
      .then((response) => {
        setCurPageNum(1);
        setCursorValues([...cursorValues, response.next_cursor ?? null]);
      })
      .catch((error) =>
        setError(new Error(`Failed to fetch Leads: ${error.message}`))
      )
      .finally(() => setLoading(false));
  }, [authContext]);

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

  return (
    <Table
      columns={columns}
      leads={curLeads}
      totalLeadsCount={totalLeadsCount}
      curPageNum={curPageNum}
      handlePageClick={handlePageClick}
      dataLoading={dataLoading}
      onCustomColumnAdded={onCustomColumnAdded}
    />
  );
};

export default LeadsTable;
