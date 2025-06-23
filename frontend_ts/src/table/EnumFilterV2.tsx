import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { CirclePlus } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { CheckedState } from "@radix-ui/react-checkbox";
import { getCustomColumnDisplayName } from "./AddCustomColumn";
import { useState } from "react";

interface EnumFilterProps {
  displayName: string; // Display name of the filter.
  allFilterValues: string[]; // All possible filter values.
  initialFilterValues: string[]; // Initial filter values.
  onFilterValuesChanged: (newFilterValues: string[]) => void; // Callback for when filter values change.
}

// Common Filter component for columns that have finite set of values (Enums)
// like Status, Type of Company etc.
const EnumFilterV2: React.FC<EnumFilterProps> = ({
  displayName,
  allFilterValues,
  initialFilterValues,
  onFilterValuesChanged,
}) => {
  const [curFilterValues, setCurFilterValues] =
    useState<string[]>(initialFilterValues);

  // Handle Checked Value change for given filter.
  const handleCheckedChange = (filterVal: string) => {
    return (checkedValue: CheckedState) => {
      var newFilterValues: string[] = [];
      if (checkedValue === true) {
        // Column Value has been checked, add column Value to current filter value.
        newFilterValues = [...curFilterValues, filterVal];
      } else {
        // Column Value has been unchecked, remove it from current value.
        newFilterValues = curFilterValues.filter((val) => val !== filterVal);
      }
      setCurFilterValues(newFilterValues);
    };
  };

  return (
    <div>
      <Popover
        onOpenChange={(open) => {
          if (!open) {
            onFilterValuesChanged(curFilterValues);
          }
        }}
      >
        <PopoverTrigger className="flex gap-4 items-center px-4 py-2 text-sm font-medium text-gray-600 rounded-md shadow-sm bg-white hover:bg-gray-100 transition duration-300 border border-gray-200">
          {/* Trigger Button */}
          <div className="flex gap-2">
            <CirclePlus size={18} />
            <span>{displayName}</span>
          </div>

          {/* Currently Selected Filters.  */}
          <div className="flex gap-1">
            {curFilterValues.map((filterVal) => (
              <Badge key={filterVal}>
                {getCustomColumnDisplayName(filterVal)}
              </Badge>
            ))}
          </div>
        </PopoverTrigger>

        {/* Popover Content */}
        <PopoverContent className="w-64 p-4 bg-white rounded-md shadow-lg border border-gray-200">
          <h3 className="text-sm font-semibold text-gray-700 mb-2">
            Filter by {displayName}
          </h3>
          <div className="space-y-2">
            {allFilterValues.map((filterVal) => (
              <div
                key={filterVal}
                className="flex items-center gap-3 p-2 rounded-md hover:bg-gray-100 transition duration-200"
              >
                <Checkbox
                  id={filterVal}
                  checked={curFilterValues.includes(filterVal)}
                  onCheckedChange={handleCheckedChange(filterVal)}
                />
                <label
                  htmlFor={filterVal}
                  className="flex justify-between items-center w-full text-sm text-gray-600"
                >
                  <span>{getCustomColumnDisplayName(filterVal)}</span>
                </label>
              </div>
            ))}
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
};

export default EnumFilterV2;
