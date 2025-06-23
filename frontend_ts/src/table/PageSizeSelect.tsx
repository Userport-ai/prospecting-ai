import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useState } from "react";

const pageLimitOptions: number[] = [20, 50, 100];

const PageSizeSelect: React.FC<{
  curPageSize: number;
  onPageSizeChange: (pageSize: number) => void;
}> = ({ curPageSize, onPageSizeChange }) => {
  const [selectedOption, setSelectedOption] = useState<string>(
    curPageSize.toString()
  );

  const onValueChange = (newOption: string) => {
    const newPageSize = Number(newOption);
    setSelectedOption(newOption);
    onPageSizeChange(newPageSize);
  };

  return (
    <div className="flex items-center gap-2">
      <p className="text-sm text-gray-600">Rows per page </p>
      <Select value={selectedOption.toString()} onValueChange={onValueChange}>
        <SelectTrigger className="w-[5rem] border border-gray-300">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            {pageLimitOptions.map((pageLimit) => (
              <SelectItem key={pageLimit} value={pageLimit.toString()}>
                {pageLimit}
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
    </div>
  );
};

export default PageSizeSelect;
