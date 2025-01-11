import { useState } from "react";
import {
  getCoreRowModel,
  useReactTable,
  getPaginationRowModel,
  getSortedRowModel,
  getFilteredRowModel,
} from "@tanstack/react-table";
import AddCustomColumn from "@/table/AddCustomColumn";
import CommonTable from "@/table/CommonTable";
import EnumFilter from "@/table/EnumFilter";
import VisibleColumns from "@/table/VisibleColumns";
import TextFilter from "@/table/TextFilter";

export function Table({ columns, data, onCustomColumnAdded }) {
  const [sorting, setSorting] = useState([]);
  const [columnFilters, setColumnFilters] = useState([]);
  const [rowSelection, setRowSelection] = useState({});
  const [pagination, setPagination] = useState({
    pageIndex: 0, //initial page index
    pageSize: 10, //default page size
  });

  var initialColumnVisibility = {};
  columns.forEach((col) => {
    initialColumnVisibility[col.accessorKey] = false;
    if (col.visibleInitially === true) {
      initialColumnVisibility[col.accessorKey] = true;
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
    state: {
      sorting,
      columnFilters,
      columnVisibility,
      rowSelection,
      pagination,
    },
  });

  const handleCustomColumnAdd = (customColumnInfo) => {
    // Fetch the rows that need to be enriched. By default,
    // we fetch all the rows on the current page.
    const rowIds = table.getRowModel().rows.map((row) => row.original.id);
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
            placeholder={"Filter Lead name..."}
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
        {/* TODO: Add Leads to the table. */}

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
}
