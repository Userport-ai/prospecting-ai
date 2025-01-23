import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { CirclePlus } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { ColumnFilter, Table } from "@tanstack/react-table";
import { CheckedState } from "@radix-ui/react-checkbox";
import { CustomColumnMeta } from "./CustomColumnMeta";

// The 'columnFilters' state contains the current global state of filters
// on the entire table. We use it to set "checked" to the correct value
// even after the Popover is closed. 'columnFilters' is of the format
// [{id: "stats", value: ["pending", "complete"]}, {id: "name", value: "Chase"}] etc.
// The ColumnId should be set to accessorKey value from the original column definition.
interface EnumFilterProps {
  table: Table<any>;
  columnId: string;
  columnFilters: ColumnFilter[];
}

// Common Filter component for columns that have finite set of values (Enums)
// like Status, Type of Company etc.
const EnumFilter: React.FC<EnumFilterProps> = ({
  table,
  columnId,
  columnFilters,
}) => {
  const column = table.getColumn(columnId);
  if (!column) {
    // Column does not exist for given columnId.
    console.error(`Column does not exist for given key: ${columnId}`);
    return null;
  }

  // Computes a map of uniques values of given column and their counts.
  const columnCountMap: Record<string, number> = table
    .getCoreRowModel()
    .rows.map((row) => row.getValue(columnId) as string)
    .reduce((map: Record<string, number>, item: string) => {
      map[item] = (map[item] || 0) + 1;
      return map;
    }, {} as Record<string, number>);

  // Is given column value already checked/selected. 'columnFilters' is of the format
  // [{id: "stats", value: ["pending", "complete"]}, {id: "name", value: "Chase"}] etc.
  // If the column value exists in this array, then it checked/selected and false otherwise.
  const isColumnValChecked = (columnVal: string) =>
    columnFilters.some(
      (curFilter) =>
        curFilter.id === columnId &&
        (curFilter.value as string[]).includes(columnVal)
    );

  // Handle Checked Value change for a given column. We need to update
  // the Column Filter accordingly to either add or remove the new value
  // from the filter.
  const handleCheckedChange = (columnVal: string) => {
    return (checkedValue: CheckedState) => {
      var curFilterValue = column.getFilterValue() as string[];
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

  const colDisplayName =
    (column.columnDef.meta as CustomColumnMeta).displayName ||
    column.columnDef.id;
  return (
    <div>
      <Popover>
        <PopoverTrigger className="flex gap-4 items-center px-4 py-2 text-sm font-medium text-gray-600 rounded-md shadow-sm bg-white hover:bg-gray-100 transition duration-300 border border-gray-200">
          {/* Trigger Button */}
          <div className="flex gap-2">
            <CirclePlus size={18} />
            <span>{colDisplayName}</span>
          </div>

          {/* Currently Selected Filters.  */}
          <div className="flex gap-1">
            {curSelectedFilter &&
              (curSelectedFilter.value as string[]).map((filterVal) => (
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
};

export default EnumFilter;
