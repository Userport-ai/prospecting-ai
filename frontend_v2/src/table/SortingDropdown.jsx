import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ChevronDown, ChevronUp, CircleX } from "lucide-react";

export default function SortingDropdown({ children, onSelect }) {
  const handleSelection = (e) => {
    const val = e.target.innerText;
    var res = "none";
    if (val === "Asc") {
      res = "asc";
    } else if (val === "Desc") {
      res = "desc";
    }
    onSelect(res);
  };
  const itemClassName =
    "flex justify-between hover:cursor-pointer focus:bg-gray-300";
  return (
    <DropdownMenu>
      <DropdownMenuTrigger>{children}</DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuLabel>Sorting Options</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem className={itemClassName} onSelect={handleSelection}>
          Asc <ChevronUp />
        </DropdownMenuItem>
        <DropdownMenuItem className={itemClassName} onSelect={handleSelection}>
          Desc <ChevronDown />
        </DropdownMenuItem>
        <DropdownMenuItem className={itemClassName} onSelect={handleSelection}>
          None <CircleX />
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
