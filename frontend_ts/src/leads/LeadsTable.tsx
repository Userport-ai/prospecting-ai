import { useEffect, useState } from "react";
import {
  getCoreRowModel,
  useReactTable,
  getPaginationRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  ColumnDef,
  ColumnSort,
  ColumnFilter,
  ColumnFiltersState,
  Updater,
} from "@tanstack/react-table";
import AddCustomColumn from "@/table/AddCustomColumn";
import {
  CustomColumnInput,
  getCustomColumnDisplayName,
} from "@/table/AddCustomColumn";
import CommonTable from "@/table/CommonTable";
import EnumFilter from "@/table/EnumFilter";
import TextFilter from "@/table/TextFilter";
import { getLeadColumns } from "./Columns";
import { CustomColumnMeta } from "@/table/CustomColumnMeta";
import { Lead as LeadRow, listSuggestedLeads } from "@/services/Leads";
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
  moreLeadsToFetch: boolean; // Whether server has more leads to fetch.
  dataLoading: boolean;
  onFetchNextPage: () => Promise<void>;
  onCustomColumnAdded: (arg0: CustomColumnInput) => void;
}

export const Table: React.FC<TableProps> = ({
  columns,
  leads,
  totalLeadsCount,
  moreLeadsToFetch,
  dataLoading,
  onFetchNextPage,
  onCustomColumnAdded,
}) => {
  const authContext = useAuthContext();
  const [sorting, setSorting] = useState<ColumnSort[]>([
    { id: "fit_score", desc: true },
  ]);

  var persona_filter_values: string[] = [];
  if (authContext.userContext?.tenant.id !== USERPORT_TENANT_ID) {
    persona_filter_values = [
      getCustomColumnDisplayName("buyer"),
      getCustomColumnDisplayName("influencer"),
      getCustomColumnDisplayName("end_user"),
      "null",
    ];
  } else {
    // Test account, so we use only the two personas here.
    // TODO: Change once this is no longer the test account.
    persona_filter_values = [
      getCustomColumnDisplayName("buyer"),
      getCustomColumnDisplayName("influencer"),
    ];
  }

  const [columnFilters, setColumnFilters] = useState<ColumnFilter[]>([
    {
      id: "persona_match",
      value: persona_filter_values,
    },
  ]);
  const [rowSelection, setRowSelection] = useState({});

  const initialPaginationState = {
    pageIndex: 0, //initial page index
    pageSize: 10, //default page size
  };
  const [pagination, setPagination] = useState(initialPaginationState);

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
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    onSortingChange: setSorting,
    onColumnFiltersChange: onColumnFiltersChange,
    onColumnVisibilityChange: setColumnVisibility,
    onRowSelectionChange: setRowSelection,
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

  // User clicks on next page button in the table.
  // We assume when this callback is called that next page on server is definitely
  // available.
  const handleNextPageClick = async () => {
    if (table.getCanNextPage()) {
      // Next page exists, just update table to next page.
      table.nextPage();
      return;
    }
    await onFetchNextPage();
    // Fetch the row model count on the current page (before next page was fetched).
    // If this is less than pageSize, then stay on the same page.
    // If equal to pageSize, go to next page.
    const currentPageRowCount = table.getRowModel().rows.length;
    if (currentPageRowCount === initialPaginationState.pageSize) {
      table.nextPage();
    }
  };

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
        pagination={pagination}
        morePagesToFetch={moreLeadsToFetch}
        handleNextPageClick={handleNextPageClick}
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
  // Latest Page number fetched from server.
  const [serverPage, setServerPage] = useState(1);
  // Whether there are more leads to fetch from server.
  const [moreLeadsToFetch, setMoreLeadsToFetch] = useState(false);
  // Total leads count found on the server.
  const [totalLeadsCount, setTotalLeadsCount] = useState(0);
  const [columns, setColumns] = useState<ColumnDef<LeadRow>[]>([]);

  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [dataLoading, setDataLoading] = useState<boolean>(false);

  // Initial fetch for leads.
  useEffect(() => {
    listSuggestedLeads(authContext, serverPage, accountId)
      .then((response) => {
        setTotalLeadsCount(response.count);
        setMoreLeadsToFetch(response.next !== null);
        setCurLeads(response.results);
        setColumns(getLeadColumns(response.results));
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

  // Handle user request to fetch the next page.
  const onFetchNextPage = async () => {
    setDataLoading(true);
    const nextPage = serverPage + 1;
    try {
      const response = await listSuggestedLeads(
        authContext,
        nextPage,
        accountId
      );
      setTotalLeadsCount(totalLeadsCount);
      setMoreLeadsToFetch(response.next !== null);
      const allLeads = [...curLeads, ...response.results];
      setCurLeads(allLeads);
      setColumns(getLeadColumns(allLeads));
      setServerPage(nextPage);
    } catch (error: any) {
      setError(
        new Error(
          `Failed to fetch Next Page: ${nextPage} for Leads: ${error.message}`
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
      moreLeadsToFetch={moreLeadsToFetch}
      dataLoading={dataLoading}
      onFetchNextPage={onFetchNextPage}
      onCustomColumnAdded={onCustomColumnAdded}
    />
  );
};

export default LeadsTable;
