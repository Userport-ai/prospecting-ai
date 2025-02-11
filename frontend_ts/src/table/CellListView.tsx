// Component that displays given list of values

import { wrapColumnContentClass } from "@/common/utils";
import { cn } from "@/lib/utils";

// in a table cell.
const CellListView: React.FC<{ values: string[] }> = ({ values }) => {
  if (values.length === 0) {
    return null;
  }
  return (
    <div className={cn("flex flex-col gap-1", wrapColumnContentClass)}>
      {values.map((value, index) => (
        <p key={value}>
          {index + 1}. {value}
        </p>
      ))}
    </div>
  );
};

export default CellListView;
