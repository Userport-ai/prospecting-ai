import { Input } from "@/components/ui/input";
import { Table } from "@tanstack/react-table";
import { ChangeEvent} from "react";

// The ColumnId should be set to accessorKey value from the original column definition.
// Placeholder is text shown on the filter box.
// Used for columns like name, description, title etc.
interface TextFilterProps {
  table: Table<any>;
  columnId: string;
  placeholder: string;
}

type InputValue = string | number | readonly string[] | undefined;

// Filtering given column using free text search.
const TextFilter: React.FC<TextFilterProps> = ({ table, columnId, placeholder }) => {
  const onChange = (e: ChangeEvent<HTMLInputElement>) => {
    const value = (e.target as HTMLInputElement).value;
    table.getColumn(columnId)?.setFilterValue(value);
  }
  return (
    <div>
      <Input
        placeholder={placeholder}
        value={(table.getColumn(columnId)?.getFilterValue() as InputValue) ?? ""}
        onChange={onChange}
        className="max-w-sm shadow-sm border-gray-300 focus:ring-primary focus:border-primary"
      />
    </div>
  );
}

export default TextFilter;
