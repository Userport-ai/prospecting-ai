import { useState } from "react";
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  getPaginationRowModel,
  getSortedRowModel,
  getFilteredRowModel,
} from "@tanstack/react-table";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { CirclePlus, Eye } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";

// Filter for columns that have finite set of values (Enums)
// like Status, Type of Company etc. The ColumnId should be
// set to accessorKey value from the original column definition.
// The 'columnFilters' state contains the current global state of filters
// on the entire table. We use it to set "checked" to the correct value
// even after the Popover is closed.
function EnumFilter({ table, columnId, columnFilters }) {
  // Computes a map of uniques values of column and their counts.
  const columnCountMap = table
    .getCoreRowModel()
    .rows.map((row) => row.getValue(columnId))
    .reduce((map, item) => {
      map[item] = (map[item] || 0) + 1;
      return map;
    }, {});

  const column = table.getColumn(columnId);
  const colDisplayName = column.columnDef.displayName
    ? table.getColumn(columnId).columnDef.displayName
    : columnId;

  // Is column value (one of the unique values among all rows) already checked.'columnFilters' is of the format
  // [{id: "stats", value: ["pending", "complete"]}, {id: "name", value: "Chase"}] etc.
  const isColumnValChecked = (columnVal) =>
    columnFilters.some(
      (curFilter) =>
        curFilter.id === columnId && curFilter.value.includes(columnVal)
    );

  // Handle Checked Value change for a given column. We need to update
  // the Column Filter accordingly to either add or remove the new value
  // from the filter.
  const handleCheckedChange = (columnVal) => {
    return (checkedValue) => {
      var curFilterValue = column.getFilterValue();
      var newFilterValue;
      if (checkedValue === true) {
        // Column Value has been checked, add column Value to current filter value.
        newFilterValue = curFilterValue
          ? curFilterValue.concat(columnVal)
          : [columnVal];
      } else {
        // Column Value has been unchecked, remove it from current value.
        newFilterValue = curFilterValue
          ? curFilterValue.filter((val) => val !== columnVal)
          : [];
      }
      column.setFilterValue(newFilterValue);
    };
  };

  // Currently selected filters for given column.
  // 'columnFilters' is of the format:
  // [{id: "stats", value: ["pending", "complete"]}, {id: "name", value: "Chase"}] etc.
  const gotFilterArr = columnFilters.filter(
    (curFilter) => curFilter.id === columnId
  );
  const curSelectedFilter = gotFilterArr.length > 0 ? gotFilterArr[0] : null;

  return (
    <div>
      <Popover>
        <PopoverTrigger className="flex gap-4 items-center px-4 py-2 text-sm font-medium text-gray-600 rounded-md shadow-sm bg-white hover:bg-gray-100 transition duration-300">
          {/* Trigger Button */}
          <div className="flex gap-2">
            <CirclePlus size={18} />
            <span>{colDisplayName}</span>
          </div>

          {/* Currently Selected Filters.  */}
          <div className="flex gap-1">
            {curSelectedFilter &&
              curSelectedFilter.value.map((filterVal) => (
                <Badge key={filterVal}>{filterVal}</Badge>
              ))}
          </div>
        </PopoverTrigger>

        {/* Popover Content */}
        <PopoverContent className="w-64 p-4 bg-white rounded-md shadow-lg border border-gray-200">
          <h3 className="text-sm font-semibold text-gray-700 mb-2">
            Filter by {colDisplayName}
          </h3>
          <div className="space-y-2">
            {Object.entries(columnCountMap).map(([columnVal, count]) => (
              <div
                key={columnVal}
                className="flex items-center gap-3 p-2 rounded-md hover:bg-gray-100 transition duration-200"
              >
                <Checkbox
                  id={columnVal}
                  checked={isColumnValChecked(columnVal)}
                  onCheckedChange={handleCheckedChange(columnVal)}
                />
                <label
                  htmlFor={columnVal}
                  className="flex justify-between items-center w-full text-sm text-gray-600"
                >
                  <span>{columnVal}</span>
                  <span className="text-gray-500 text-xs">{count}</span>
                </label>
              </div>
            ))}
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
}

export function DataTable({ columns, data }) {
  const [sorting, setSorting] = useState([]);
  const [columnFilters, setColumnFilters] = useState([]);
  const [rowSelection, setRowSelection] = useState({});

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
    state: {
      sorting,
      columnFilters,
      columnVisibility,
      rowSelection,
    },
  });

  // We use total column width (in pixel values) to set the Table Width in CSS.
  // We cannot set className as 'w-[total width]px` since TailwindCSS does not
  // allow for string interpolation created classnames per: https://tailwindcss.com/docs/content-configuration#dynamic-class-names
  // Instead we set the table width as an inline style per https://stackoverflow.com/questions/76855056/unable-to-set-arbitrary-value-for-a-background-in-tailwindcss.
  const totalColumnsWidth = table.getCenterTotalSize();

  return (
    <div className="flex flex-col gap-4">
      {/* Filter Controls */}
      <div className="flex gap-4">
        <div>
          {/* Name Filter */}
          <Input
            placeholder="Filter Account name..."
            value={table.getColumn("name")?.getFilterValue() ?? ""}
            onChange={(event) =>
              table.getColumn("name")?.setFilterValue(event.target.value)
            }
            className="max-w-sm shadow-sm border-gray-300 focus:ring-primary focus:border-primary"
          />
        </div>

        {/* Status Filter */}
        <EnumFilter
          table={table}
          columnId={"status"}
          columnFilters={columnFilters}
        />
      </div>

      {/* Column Visibility */}
      <div>
        <Popover>
          <PopoverTrigger className="flex gap-2 items-center px-4 py-2 text-sm font-medium text-gray-600 rounded-md shadow-sm bg-white hover:bg-gray-100 transition duration-300">
            <Eye size={18} />
            <span>Visible Columns</span>
          </PopoverTrigger>
          <PopoverContent align="start" className="w-fit p-4">
            {table
              .getAllColumns()
              .filter((column) => column.getCanHide())
              .map((column) => (
                <div
                  key={column.id}
                  className="flex items-center gap-4 p-2 rounded-md hover:bg-gray-100 transition duration-200"
                >
                  <Checkbox
                    checked={column.getIsVisible()}
                    onCheckedChange={(value) => column.toggleVisibility(value)}
                  />
                  <label className="flex justify-between items-center w-full text-sm text-gray-600">
                    {column.id}
                  </label>
                </div>
              ))}
          </PopoverContent>
        </Popover>
      </div>

      {/* Table Container */}
      <div className="rounded-md border w-fit border-gray-300 bg-white shadow-sm">
        <Table style={{ width: `${totalColumnsWidth.toString()}px` }}>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead
                    key={header.id}
                    className="bg-[rgb(104,93,133)] text-white font-semibold px-4 py-2"
                  >
                    <div className="flex justify-between items-center">
                      {header.isPlaceholder
                        ? null
                        : flexRender(
                            header.column.columnDef.header,
                            header.getContext()
                          )}

                      {/* Column resize button */}
                      <div
                        {...{
                          onDoubleClick: () => header.column.resetSize(),
                          onMouseDown: header.getResizeHandler(),
                          onTouchStart: header.getResizeHandler(),
                          className: `resizer ${
                            table.options.columnResizeDirection
                          } ${
                            header.column.getIsResizing() ? "isResizing" : ""
                          }`,
                          style: {
                            transform:
                              columnResizeMode === "onEnd" &&
                              header.column.getIsResizing()
                                ? `translateX(${
                                    (table.options.columnResizeDirection ===
                                    "rtl"
                                      ? -1
                                      : 1) *
                                    (table.getState().columnSizingInfo
                                      .deltaOffset ?? 0)
                                  }px)`
                                : "",
                          },
                        }}
                      />
                    </div>
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() && "selected"}
                  className="hover:bg-gray-100 transition-colors data-[state=selected]:bg-purple-50"
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell
                      key={cell.id}
                      style={{ width: cell.column.getSize() }}
                      className="text-gray-700 px-4 py-2"
                    >
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center text-gray-500"
                >
                  No results.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Selected Rows Information */}
      {table.getFilteredSelectedRowModel().rows.length > 0 && (
        <div className="flex p-1 text-sm text-muted-foreground">
          {table.getFilteredSelectedRowModel().rows.length} of{" "}
          {table.getFilteredRowModel().rows.length} row(s) selected.
        </div>
      )}

      {/* Pagination Controls */}
      <div className="flex items-center justify-start space-x-4">
        <Button
          variant="outline"
          size="sm"
          onClick={() => table.previousPage()}
          disabled={!table.getCanPreviousPage()}
          className="shadow-sm border-gray-300"
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => table.nextPage()}
          disabled={!table.getCanNextPage()}
          className="shadow-sm border-gray-300"
        >
          Next
        </Button>
      </div>
    </div>
  );
}
