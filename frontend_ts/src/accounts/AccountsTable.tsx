import React, { useEffect, useState } from "react";
import {
  getCoreRowModel,
  useReactTable,
  getSortedRowModel,
  getFilteredRowModel,
  ColumnDef,
  ColumnSort,
  ColumnFilter,
} from "@tanstack/react-table";
import AddCustomColumn from "@/table/AddCustomColumn";
import { CustomColumnInput } from "@/table/AddCustomColumn";
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
import LoadingOverlay from "@/common/LoadingOverlay";

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
  onPollingComplete: (accounts: AccountRow[]) => void;
}

// Component to Poll Accounts that are in pending state.
const PollPendingAccounts: React.FC<PollPendingAccountsProps> = ({
  accounts,
  onPollingComplete,
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
    const intervalId = setInterval(async () => {
      const response = await listAccounts(authContext, { ids: pollAccountIds });
      const newPolledAccounts = response.results;
      onPollingComplete(newPolledAccounts);
    }, POLLING_INTERVAL);
    return () => clearInterval(intervalId);
  }, [pollAccountIds]);
  return null;
};

interface TableProps {
  columns: ColumnDef<AccountRow>[];
  accounts: AccountRow[];
  totalAccountsCount: number;
  curPageNum: number;
  handlePageClick: (goToNextPage: boolean) => Promise<void>;
  dataLoading: boolean;
  onCustomColumnAdded: (arg0: CustomColumnInput) => void;
  curPageSize: number;
  onPageSizeChange: (pageSize: number) => void;
}

// Component to display Accounts Table.
const Table: React.FC<TableProps> = ({
  columns,
  accounts,
  totalAccountsCount,
  curPageNum,
  handlePageClick,
  dataLoading,
  onCustomColumnAdded,
  curPageSize,
  onPageSizeChange,
}) => {
  const [sorting, setSorting] = useState<ColumnSort[]>([]);
  const [columnFilters, setColumnFilters] = useState<ColumnFilter[]>([]);
  const [rowSelection, setRowSelection] = useState<Record<string, boolean>>({});
  const pageCount = Math.ceil(totalAccountsCount / curPageSize);

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

  const handleCustomColumnAdd = (customColumnInfo: CustomColumnInput) => {
    // Fetch the rows that need to be enriched. By default,
    // we fetch all the rows on the current page.
    const rowIds = table
      .getRowModel()
      .rows.map((row) => (row.original as AccountRow).id ?? "");
    customColumnInfo.rowIds = rowIds;
    onCustomColumnAdded(customColumnInfo);
  };

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
        headerClassName="bg-[rgb(122,103,171)]"
        curPageSize={curPageSize}
        onPageSizeChange={onPageSizeChange}
      />

      <LoadingOverlay loading={dataLoading} />
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
  // Total cccounts count found on the server.
  const [totalAccountsCount, setTotalAccountsCount] = useState(0);
  const [columns, setColumns] = useState<ColumnDef<AccountRow>[]>([]);

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);
  const [dataLoading, setDataLoading] = useState<boolean>(false);

  const listAccountsHelper = async (pageNum: number) => {
    const response = await listAccounts(authContext, {
      page: pageNum,
      page_size: curPageSize,
    });
    setTotalAccountsCount(response.count);
    setCurAccounts(response.results);
    setColumns(getAccountColumns(response.results));
    setCurPageNum(pageNum);
  };

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

  if (loading) {
    return <ScreenLoader />;
  }

  if (error) {
    throw error;
  }

  // Handler for when a single polling request is completed.
  const onPollingComplete = (polledAccounts: AccountRow[]) => {
    // Stored the polled accounts in a map.
    const polledAccountsMap: Record<string, AccountRow> = polledAccounts.reduce(
      (curAccMap, account) => ({ ...curAccMap, [account.id]: account }),
      {} as Record<string, AccountRow>
    );
    // Update only the accounts that were polled.
    const updatedAccounts = curAccounts.map((account) =>
      account.id in polledAccountsMap ? polledAccountsMap[account.id] : account
    );
    setCurAccounts(updatedAccounts);
  };

  // Accounts added by the user which have been successfully created by the API as well.
  const onAccountsAdded = (addedAccounts: AccountRow[]) => {
    setCurAccounts([...addedAccounts, ...curAccounts]);
  };

  // Handler for when custom column inputs are provided by the user.
  const onCustomColumnAdded = (customColumnInfo: CustomColumnInput) => {
    // TODO: call server to send custom column request instead
    console.log("custom colum info ", customColumnInfo);
  };

  // Handle user request to go to page.
  // If goToNextPage is true, fetch next page, otherwise fetch previous page.
  // We assume this callback can be called only if next or prev page buttons
  // are enabled in the UI. In other words, we assume those validations are already done.
  const handlePageClick = async (goToNextPage: boolean) => {
    setDataLoading(true);
    const nextPageNum = goToNextPage ? curPageNum + 1 : curPageNum - 1;
    try {
      await listAccountsHelper(nextPageNum);
    } catch (error: any) {
      setError(
        new Error(
          `Failed to Accounts fetch nextPage: ${goToNextPage} with next page num: ${nextPageNum} with error: ${error.message}`
        )
      );
    } finally {
      setDataLoading(false);
    }
  };

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
      </div>

      <Separator className="my-4 bg-gray-300" />

      <Table
        columns={columns}
        accounts={curAccounts}
        totalAccountsCount={totalAccountsCount}
        curPageNum={curPageNum}
        handlePageClick={handlePageClick}
        dataLoading={dataLoading}
        onCustomColumnAdded={onCustomColumnAdded}
        curPageSize={curPageSize}
        onPageSizeChange={setCurPageSize}
      />
    </div>
  );
}
