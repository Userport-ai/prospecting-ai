import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ColumnDef, flexRender } from "@tanstack/react-table";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Table as TanstackTable } from "@tanstack/react-table";
import { cn } from "@/lib/utils";

interface CommonTableProps<T> {
  table: TanstackTable<T>;
  columns: ColumnDef<T>[];
  columnResizeMode: string;
  pagination: { pageIndex: number };
  headerClassName?: string;
}

// Common Table component that renders a common table used by Accounts and Leads.
// Takes a Tanstack table object, columns, resize mode and paginations as inputs to populate the data.
const CommonTable: React.FC<CommonTableProps<any>> = ({
  table,
  columns,
  columnResizeMode,
  pagination,
  headerClassName,
}) => {
  // We use total column width (in pixel values) to set the Table Width in CSS.
  // We cannot set className as 'w-[total width]px` since TailwindCSS does not
  // allow for string interpolation created classnames per: https://tailwindcss.com/docs/content-configuration#dynamic-class-names
  // Instead we set the table width as an inline style per https://stackoverflow.com/questions/76855056/unable-to-set-arbitrary-value-for-a-background-in-tailwindcss.
  const totalColumnsWidth = table.getCenterTotalSize();

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-md border w-fit border-gray-300 bg-white shadow-sm">
        <div
          className="max-w-[80rem] min-w-full overflow-x-auto" // Ensures content width adapts dynamically
        >
          <Table style={{ width: totalColumnsWidth }}>
            {/* Header */}
            <TableHeader>
              {table.getHeaderGroups().map((headerGroup) => (
                <TableRow key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <TableHead
                      key={header.id}
                      style={{
                        // When this is not working,
                        // got to https://github.com/TanStack/table/issues/5115.
                        width: header.getSize(),
                      }}
                      className={cn(
                        "text-white font-semibold px-2 py-1 border-b border-purple-300",
                        headerClassName
                      )}
                    >
                      <div className="flex justify-between items-center">
                        {header.isPlaceholder
                          ? null
                          : flexRender(
                              header.column.columnDef.header,
                              header.getContext()
                            )}

                        {/* Column resize button, CSS in index.css */}
                        <button
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

            {/* Rows */}
            <TableBody>
              {table.getRowModel().rows?.length ? (
                table.getRowModel().rows.map((row) => (
                  <TableRow
                    key={row.id}
                    data-state={row.getIsSelected() && "selected"}
                    className="hover:bg-gray-50 transition-colors data-[state=selected]:bg-purple-50"
                  >
                    {row.getVisibleCells().map((cell) => (
                      <TableCell
                        key={cell.id}
                        style={{ width: cell.column.getSize() }}
                        className="text-gray-700 px-2 py-2"
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
      </div>

      {/* Selected Rows Information */}
      <div className="flex p-1 text-sm text-muted-foreground">
        {table.getFilteredSelectedRowModel().rows.length} of{" "}
        {table.getFilteredRowModel().rows.length} row(s) selected.
      </div>

      {/* Pagination Controls */}
      <div className="flex items-center justify-start gap-4">
        <div>
          <p className=" text-sm text-gray-600">
            Page {pagination.pageIndex + 1} of {table.getPageCount()}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => table.previousPage()}
          disabled={!table.getCanPreviousPage()}
          className="shadow-sm border-gray-300"
        >
          <ChevronLeft />
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => table.nextPage()}
          disabled={!table.getCanNextPage()}
          className="shadow-sm border-gray-300"
        >
          <ChevronRight />
        </Button>
      </div>
    </div>
  );
};

export default CommonTable;
