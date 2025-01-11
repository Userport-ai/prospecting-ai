import { Input } from "@/components/ui/input";

// Filtering given column using free text search.
// Table input is a Tanstack table object.
//  The ColumnId should be set to accessorKey value from the original column definition.
// Placeholder is text shown on the filter box.
// Used for columns like name, description, title etc.
export default function TextFilter({ table, columnId, placeholder }) {
  return (
    <div>
      <Input
        placeholder={placeholder}
        value={table.getColumn(columnId)?.getFilterValue() ?? ""}
        onChange={(event) =>
          table.getColumn(columnId)?.setFilterValue(event.target.value)
        }
        className="max-w-sm shadow-sm border-gray-300 focus:ring-primary focus:border-primary"
      />
    </div>
  );
}
