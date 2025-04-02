import React, { useEffect, useState } from "react";
import {
  ColumnDef,
  ColumnFilter,
  ColumnSort,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { CustomColumn } from "@/services/CustomColumn";
import { Button } from "@/components/ui/button";
import AddAccounts from "./AddAccounts";
import CommonTable from "@/table/CommonTable";
import VisibleColumns from "@/table/VisibleColumns";
import TextFilter from "@/table/TextFilter";
import { getAccountColumns } from "./Columns";
import { CustomColumnMeta } from "@/table/CustomColumnMeta";
import { Account as AccountRow, listAccounts } from "@/services/Accounts";
import { useAuthContext } from "@/auth/AuthProvider";
import ScreenLoader from "@/common/ScreenLoader";
import { listProducts, Product } from "@/services/Products";
import { Separator } from "@/components/ui/separator";
import CreateCustomColumnDialog from "@/components/custom-columns/CustomColumnDialog";
import LoadingOverlay from "@/common/LoadingOverlay";
import {Cpu, Loader2} from "lucide-react";

const ZeroStateDisplay = () => {
  return (
    <div className="flex flex-col gap-2 items-center justify-center h-64 text-center bg-gray-50 border border-dashed border-gray-300 rounded-md p-6">
      <div className="text-gray-600 flex flex-col gap-4">
        <div className="text-xl font-semibold">No Data Available</div>
        <div className="text-md">Add Accounts to start Outreach.</div>
      </div>
    </div>
  );
};

interface PollPendingAccountsProps {
  accounts: AccountRow[];
  onPollingComplete: (accounts: AccountRow[]) => void
}

// Component to Poll Accounts that are in pending state.
const PollPendingAccounts: React.FC<PollPendingAccountsProps> = ({
                                                                   accounts,
                                                                   onPollingComplete
                                                                 }) => {
  const authContext = useAuthContext();

  // Setup polling in the background in case any of the accounts have enrichment
  // status as pending or in progress.
  const pollAccountIds: string[] = accounts
      .filter(
          (account) =>
              account.enrichment_status.total_enrichments === 0 ||
              account.enrichment_status.in_progress > 0 ||
              account.enrichment_status.pending > 0
      )
      .map((account) => account.id);

  const POLLING_INTERVAL = 30 * 1000; // Poll every 30s.

  useEffect(() => {
    if (pollAccountIds.length === 0) {
      // No accounts to poll.
      return;
    }

    console.log(`Setting up polling for ${pollAccountIds.length} accounts`);

    const intervalId = setInterval(async () => {
      console.log(`Polling ${pollAccountIds.length} accounts...`);

      try {
        const response = await listAccounts(authContext, { ids: pollAccountIds });
        const newPolledAccounts = response.results;

        console.log(`Received ${newPolledAccounts.length} accounts from polling`);

        // Only trigger refresh if there are accounts to update
        if (newPolledAccounts.length > 0) {
          onPollingComplete(newPolledAccounts);
        }
      } catch (error) {
        console.error("Error during account polling:", error);
      }
    }, POLLING_INTERVAL);

    // Clean up the interval when the component unmounts
    return () => {
      console.log("Cleaning up account polling interval");
      clearInterval(intervalId);
    };
  }, [pollAccountIds.length]); // Only re-establish polling when the number of accounts to poll changes

  return null;
};

interface TableProps {
  columns: ColumnDef<AccountRow>[];
  accounts: AccountRow[];
  totalAccountsCount: number;
  curPageNum: number;
  handlePageClick: (goToNextPage: boolean) => Promise<void>;
  dataLoading: boolean;
  curPageSize: number;
  onPageSizeChange: (pageSize: number) => void;
  isCreateColumnDialogOpen: boolean;
  onCreateColumnOpenChange: (open: boolean) => void;
  onColumnCreated: (newColumn: CustomColumn) => void;
}

// Component to display Accounts Table.
const Table: React.FC<TableProps> = ({
                                       columns,
                                       accounts,
                                       totalAccountsCount,
                                       curPageNum,
                                       handlePageClick,
                                       dataLoading,
                                       curPageSize,
                                       onPageSizeChange,
                                       isCreateColumnDialogOpen,
                                       onCreateColumnOpenChange,
                                       onColumnCreated,
                                     }) => {
  const [sorting, setSorting] = useState<ColumnSort[]>([]);
  const [columnFilters, setColumnFilters] = useState<ColumnFilter[]>([]);
  const [rowSelection, setRowSelection] = useState<Record<string, boolean>>({});
  const pageCount = Math.ceil(totalAccountsCount / curPageSize);

  // Initialize column visibility settings
  const initialColumnVisibility: Record<string, boolean> = {};
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
    data: accounts,
    columns,
    columnResizeMode,
    columnResizeDirection,
    getCoreRowModel: getCoreRowModel(),
    pageCount: pageCount,
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onColumnVisibilityChange: setColumnVisibility,
    onRowSelectionChange: setRowSelection,
    getRowId: (row) => row.id, //use the account's ID
    // Needed to solve this error: https://github.com/TanStack/table/issues/5026.
    autoResetPageIndex: false,
    state: {
      sorting,
      columnFilters,
      columnVisibility,
      rowSelection,
    },
  });

  if (accounts.length === 0) {
    // No accounts found.
    return <ZeroStateDisplay />;
  }

  return (
      <div className="flex flex-col gap-6">
        <p className="text-gray-700 text-md mb-2">
          Total Number of Accounts:{" "}
          <span className="font-semibold">{totalAccountsCount}</span>
        </p>
        <div className="flex items-center gap-6">
          {/* Filter Controls */}
          <div className="flex gap-4">
            <TextFilter
                table={table}
                columnId={"name"}
                placeholder={"Filter Account name..."}
            />
          </div>

          {/* View visible Columns. */}
          <VisibleColumns table={table} />

          {/* Add custom column */}
          <Button
              onClick={() => onCreateColumnOpenChange(true)}
              variant="outline"
              className="flex gap-2 items-center px-4 py-2 text-sm font-medium text-gray-600 rounded-md shadow-sm bg-white hover:bg-gray-100 transition duration-300 border-gray-200"
          >
            <Cpu size={16} /> Ask AI
          </Button>

          <CreateCustomColumnDialog
              open={isCreateColumnDialogOpen}
              onOpenChange={onCreateColumnOpenChange}
              onSuccess={onColumnCreated}
          />
        </div>

        {/* Table Container */}
        <CommonTable
            table={table}
            columns={columns}
            columnResizeMode={columnResizeMode}
            curPageNum={curPageNum}
            totalPageCount={pageCount}
            handlePageClick={handlePageClick}
            headerClassName="bg-[rgb(122,103,171)]"
            curPageSize={curPageSize}
            onPageSizeChange={onPageSizeChange}
        />

        {/* Replace full-screen loading with a more subtle indicator */}
        {dataLoading && (
            <div className="fixed bottom-4 right-4 bg-white shadow-md rounded-lg p-2 border border-gray-200 flex items-center text-sm text-gray-600 z-50">
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Loading data...
            </div>
        )}
      </div>
  );
};
// Displays list of accounts in a table format.
export default function AccountsTable() {
  const authContext = useAuthContext();
  // Current list of all Accounts fetched from server so far in the correct pagination order.
  const [curAccounts, setCurAccounts] = useState<AccountRow[]>([]);
  // Current Page number (fetched from server). Valid page numbers start from 1.
  const [curPageNum, setCurPageNum] = useState(0);
  // Current page size.
  const [curPageSize, setCurPageSize] = useState<number>(20);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);
  const [dataLoading, setDataLoading] = useState<boolean>(false);
  const [isCreateColumnDialogOpen, setCreateColumnDialogOpen] = useState(false);
  // Total accounts count found on the server.
  const [totalAccountsCount, setTotalAccountsCount] = useState(0);
  const [columns, setColumns] = useState<ColumnDef<AccountRow>[]>([]);
  const [backgroundRefreshing, setBackgroundRefreshing] = useState(false);

  // Function to refresh table data (accounts) in the background without full loading overlay
  const refreshTableData = async () => {
    // Only show loading indicator if not a background refresh
    setBackgroundRefreshing(true);

    try {
      // Get the current page number to maintain pagination state
      const currentPageNum = curPageNum;

      const response = await listAccounts(authContext, {
        page: currentPageNum,
        page_size: curPageSize,
      });

      // Update data without changing page
      setTotalAccountsCount(response.count);
      setCurAccounts(response.results);

      // Update columns while preserving the current page
      setColumns(getAccountColumns(response.results, refreshTableData));
    } catch (error: any) {
      console.error("Failed to refresh account table:", error);
      // Optionally show a toast notification instead of setting error state
      // toast.error(`Failed to refresh: ${error.message}`);
    } finally {
      setBackgroundRefreshing(false);
    }
  };

  // Original function for initial page load and explicit page navigation
  const listAccountsHelper = async (pageNum: number, showLoadingOverlay = true) => {
    // Always use full loading overlay for initial data fetch (when curPageNum is 0)
    const useFullLoading = showLoadingOverlay || curPageNum === 0;

    if (useFullLoading) {
      setDataLoading(true);
    } else {
      setBackgroundRefreshing(true);
    }

    try {
      const response = await listAccounts(authContext, {
        page: pageNum,
        page_size: curPageSize,
      });

      setTotalAccountsCount(response.count);
      setCurAccounts(response.results);
      setColumns(getAccountColumns(response.results, refreshTableData));
      setCurPageNum(pageNum);

      return response;
    } catch (error: any) {
      console.error(`Failed to fetch Accounts: ${error.message}`);
      throw error;
    } finally {
      if (useFullLoading) {
        setDataLoading(false);
      } else {
        setBackgroundRefreshing(false);
      }
    }
  };

  // Initial data fetch
  useEffect(() => {
    setLoading(true);
    listAccountsHelper(1)
        .then(async () => {
          const products = await listProducts(authContext);
          setProducts(products);
        })
        .catch((error) =>
            setError(new Error(`Failed to fetch Accounts: ${error.message}`))
        )
        .finally(() => setLoading(false));
  }, [authContext, curPageSize]);

  // Handle user request to go to page with improved loading
  const handlePageClick = async (goToNextPage: boolean) => {
    setDataLoading(true);
    const nextPageNum = goToNextPage ? curPageNum + 1 : curPageNum - 1;

    try {
      await listAccountsHelper(nextPageNum);
    } catch (error: any) {
      setError(
          new Error(
              `Failed to fetch Accounts for page ${nextPageNum}: ${error.message}`
          )
      );
    } finally {
      setDataLoading(false);
    }
  };

  // Handler for when a single polling request is completed.
  const onPollingComplete = (polledAccounts: AccountRow[]) => {
    // Only update if we have accounts to update
    if (polledAccounts.length === 0) return;

    // Set a subtle indicator that background refreshing is happening
    setBackgroundRefreshing(true);

    try {
      // Stored the polled accounts in a map.
      const polledAccountsMap: Record<string, AccountRow> = polledAccounts.reduce(
          (curAccMap, account) => ({ ...curAccMap, [account.id]: account }),
          {} as Record<string, AccountRow>
      );

      // Update only the accounts that were polled.
      const updatedAccounts = curAccounts.map((account) =>
          account.id in polledAccountsMap ? polledAccountsMap[account.id] : account
      );

      // Update the accounts without changing the page
      setCurAccounts(updatedAccounts);

      // Also update the columns to ensure any custom column data is refreshed
      // But maintain the current page and state
      setColumns(getAccountColumns(updatedAccounts, refreshTableData));
    } catch (error) {
      console.error("Error updating polled accounts:", error);
    } finally {
      setBackgroundRefreshing(false);
    }
  };

  // Accounts added by the user which have been successfully created by the API as well.
  const onAccountsAdded = (addedAccounts: AccountRow[]) => {
    setCurAccounts([...addedAccounts, ...curAccounts]);
  };

  const handleColumnCreated = (newColumn: CustomColumn) => {
    console.log("Custom column created:", newColumn);
    // Optional: Show a success toast/notification
    // Optional: You might want to refresh the accounts list *after a delay*
    //           to allow the backend to start populating values, or add the
    //           column definition immediately to the table state (though cells will be empty initially).
    //           Simplest approach for now might be just closing the dialog.
    setCreateColumnDialogOpen(false);

    // Example: Trigger a refresh after a short delay
    // setTimeout(() => listAccountsHelper(curPageNum || 1), 2000);
  };

  if (loading) {
    return <ScreenLoader />;
  }

  if (error) {
    throw error;
  }

  return (
      <div className="px-4 mt-2">
        <PollPendingAccounts
            accounts={curAccounts}
            onPollingComplete={onPollingComplete}
        />
        <div className="flex items-center gap-4">
          <h1 className="font-bold text-gray-600 text-2xl">Accounts</h1>
          {/* Add Accounts to the table. */}
          <AddAccounts products={products} onAccountsAdded={onAccountsAdded} />

          {/* Subtle background refresh indicator */}
          {backgroundRefreshing && (
              <div className="text-xs text-gray-500 flex items-center">
                <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                Refreshing...
              </div>
          )}
        </div>

        <Separator className="my-4 bg-gray-300" />

        <Table
            columns={columns}
            accounts={curAccounts}
            totalAccountsCount={totalAccountsCount}
            curPageNum={curPageNum}
            handlePageClick={handlePageClick}
            dataLoading={dataLoading}
            curPageSize={curPageSize}
            onPageSizeChange={setCurPageSize}
            isCreateColumnDialogOpen={isCreateColumnDialogOpen}
            onCreateColumnOpenChange={setCreateColumnDialogOpen}
            onColumnCreated={handleColumnCreated}
        />
      </div>
  );
}
