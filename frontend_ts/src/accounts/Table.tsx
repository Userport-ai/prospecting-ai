import { useState } from "react";
import {
  getCoreRowModel,
  useReactTable,
  getPaginationRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  ColumnDef,
  ColumnSort,
  ColumnFilter,
  AccessorKeyColumnDefBase,
} from "@tanstack/react-table";
import AddCustomColumn, { CustomColumnInput } from "@/table/AddCustomColumn";
import AddAccounts from "./AddAccounts";
import CommonTable from "@/table/CommonTable";
import EnumFilter from "@/table/EnumFilter";
import VisibleColumns from "@/table/VisibleColumns";
import TextFilter from "@/table/TextFilter";
import { accountColumns, AccountTableRow } from "./Columns";
import { CustomColumnMeta } from "@/table/CustomColumnMeta";
import { getData } from "./MockData";

const ZeroStateDisplay = () => {
  return (
    <div className="flex flex-col gap-2 items-center justify-center h-64 text-center bg-gray-50 border border-dashed border-gray-300 rounded-md p-6">
      <div className="text-gray-600 mb-4">
        <div className="text-xl font-semibold">No Data Available</div>
        <div className="text-sm">Add Accounts to start Outreach.</div>
      </div>
      <AddAccounts />
    </div>
  );
};

interface TableProps {
  columns: ColumnDef<AccountTableRow>[];
  data: AccountTableRow[];
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
    const accessoryKey = (col as AccessorKeyColumnDefBase<AccountTableRow>)
      .accessorKey;
    initialColumnVisibility[accessoryKey] = false;
    if ((col.meta as CustomColumnMeta).visibleInitially === true) {
      initialColumnVisibility[accessoryKey] = true;
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
      .rows.map((row) => (row.original as AccountTableRow).id ?? "");
    customColumnInfo.rowIds = rowIds;
    onCustomColumnAdded(customColumnInfo);
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex gap-4">
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
            columnId={"status"}
            columnFilters={columnFilters}
          />
        </div>

        {/* View visible Columns. */}
        <VisibleColumns table={table} />
      </div>

      <div className="flex mt-2 gap-6">
        {/* Add Accounts to the table. */}
        <AddAccounts />

        {/* Add custom column */}
        <AddCustomColumn onAdded={handleCustomColumnAdd} />
      </div>

      {/* Table Container */}
      <CommonTable
        table={table}
        columns={columns}
        columnResizeMode={columnResizeMode}
        pagination={pagination}
      />
    </div>
  );
};

export default function Accounts() {
  const [data, setData] = useState<AccountTableRow[]>(getData());
  const [columns, setColumns] =
    useState<ColumnDef<AccountTableRow>[]>(accountColumns);

  // Handler for when custom column inputs are provided by the user.
  const onCustomColumnAdded = (customColumnInfo: CustomColumnInput) => {
    // TODO: call server to send custom column request instead
    // of manually updating the columns and rows in the table.
    const customColumnAccessorKey = "custom_column";
    setColumns([
      ...columns,
      {
        accessorKey: customColumnAccessorKey,
        header: customColumnInfo.columnName,
        size: 100,
        filterFn: "arrIncludesSome",
        meta: {
          displayName: customColumnInfo.columnName,
          visibleInitially: true,
        },
      },
    ]);
    // Update columns for given RowIds with added column value.
    const rowIds = customColumnInfo.rowIds;
    if (!rowIds) {
      console.error("Error! No rows selected!");
      return;
    }
    var newData = [...data];
    newData.forEach((row) => {
      if (row.id && rowIds.includes(row.id)) {
        row[customColumnAccessorKey] = "pending";
      }
    });
    setData(newData);
  };

  return (
    <div className="w-11/12 mx-auto py-2">
      <h1 className="font-bold text-gray-700 text-2xl mb-5">Accounts</h1>
      <Table
        columns={columns}
        data={data}
        onCustomColumnAdded={onCustomColumnAdded}
      />
    </div>
  );
}
