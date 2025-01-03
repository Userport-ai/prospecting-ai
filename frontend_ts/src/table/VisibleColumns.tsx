import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Eye } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { Table} from "@tanstack/react-table";
import React from "react";
import { CustomColumnMeta } from "./CustomColumnMeta";

// Columns that are currently visible to the user in the given tanstack table.
const VisibleColumns: React.FC<{table: Table<any>}> = ({ table }) => {
  return (
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
                  onCheckedChange={(value) => column.toggleVisibility(value === true)}
                />
                <label className="flex justify-between items-center w-full text-sm text-gray-600">
                  {(column.columnDef.meta as CustomColumnMeta).displayName || column.columnDef.id}
                </label>
              </div>
            ))}
        </PopoverContent>
      </Popover>
    </div>
  );
}

export default VisibleColumns;
