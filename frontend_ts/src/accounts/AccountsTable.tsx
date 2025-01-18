import React, { useEffect, useState } from "react";
import {
  getCoreRowModel,
  useReactTable,
  getPaginationRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  ColumnDef,
  ColumnSort,
  ColumnFilter,
} from "@tanstack/react-table";
import AddCustomColumn, { CustomColumnInput } from "@/table/AddCustomColumn";
import AddAccounts from "./AddAccounts";
import CommonTable from "@/table/CommonTable";
import EnumFilter from "@/table/EnumFilter";
import VisibleColumns from "@/table/VisibleColumns";
import TextFilter from "@/table/TextFilter";
import { getAccountColumns } from "./Columns";
import { CustomColumnMeta } from "@/table/CustomColumnMeta";
import { Account as AccountRow, listAccounts } from "@/services/Accounts";
import { useAuthContext } from "@/auth/AuthProvider";
import ScreenLoader from "@/common/ScreenLoader";
import { listProducts, Product } from "@/services/Products";
import { Separator } from "@/components/ui/separator";

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
      const newPolledAccounts = await listAccounts(authContext, pollAccountIds);
      onPollingComplete(newPolledAccounts);
    }, POLLING_INTERVAL);
    return () => clearInterval(intervalId);
  }, [pollAccountIds]);
  return null;
};

interface TableProps {
  columns: ColumnDef<AccountRow>[];
  data: AccountRow[];
  onCustomColumnAdded: (arg0: CustomColumnInput) => void;
}

// Component to display Accounts Table.
const Table: React.FC<TableProps> = ({
  columns,
  data,
  onCustomColumnAdded,
}) => {
  const [sorting, setSorting] = useState<ColumnSort[]>([]);
  const [columnFilters, setColumnFilters] = useState<ColumnFilter[]>([]);
  const [rowSelection, setRowSelection] = useState({});
  const [pagination, setPagination] = useState({
    pageIndex: 0, //initial page index
    pageSize: 10, //default page size
  });

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
    data,
    columns,
    columnResizeMode,
    columnResizeDirection,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
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

  if (data.length === 0) {
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
      <div className="flex items-center gap-6">
        {/* Filter Controls */}
        <div className="flex gap-4">
          <TextFilter
            table={table}
            columnId={"name"}
            placeholder={"Filter Account name..."}
          />

          {/* Status Filter */}
          <EnumFilter
            table={table}
            columnId={"enrichment_status"}
            columnFilters={columnFilters}
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
        pagination={pagination}
        headerClassName="bg-[rgb(122,103,171)]"
      />
    </div>
  );
};

// Displays list of accounts in a table format.
export default function AccountsTable() {
  const authContext = useAuthContext();
  const [loading, setLoading] = useState<boolean>(true);
  const [accounts, setAccounts] = useState<AccountRow[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [columns, setColumns] = useState<ColumnDef<AccountRow>[]>([]);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    listAccounts(authContext)
      .then(async (accounts) => {
        const products = await listProducts(authContext);
        setAccounts(accounts);
        setColumns(getAccountColumns(accounts));
        setProducts(products);
      })
      .catch((error) =>
        setError(new Error(`Failed to fetch Accounts: ${error.message}`))
      )
      .finally(() => setLoading(false));
  }, [authContext]);

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
    const updatedAccounts = accounts.map((account) =>
      account.id in polledAccountsMap ? polledAccountsMap[account.id] : account
    );
    setAccounts(updatedAccounts);
  };

  // Accounts added by the user which have been successfully created by the API as well.
  const onAccountsAdded = (addedAccounts: AccountRow[]) => {
    setAccounts([...addedAccounts, ...accounts]);
  };

  // Handler for when custom column inputs are provided by the user.
  const onCustomColumnAdded = (customColumnInfo: CustomColumnInput) => {
    // TODO: call server to send custom column request instead
    console.log("custom colum info ", customColumnInfo);
  };

  return (
    <div className="px-4 mt-2">
      <PollPendingAccounts
        accounts={accounts}
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
        data={accounts}
        onCustomColumnAdded={onCustomColumnAdded}
      />
    </div>
  );
}
