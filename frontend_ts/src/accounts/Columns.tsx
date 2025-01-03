import { ChevronsUpDown, ExternalLink } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import SortingDropdown from "../table/SortingDropdown";
import { ColumnDef, Table } from "@tanstack/react-table";
import { ReactNode } from "react";
import { CustomColumnMeta } from "@/table/CustomColumnMeta";

interface BaseAccountTableRow {
  id: string;
  select?: ReactNode;
  name: ReactNode;
  status: string;
  location?: string;
  employee_count?: number;
  customers?: string;
  technologies?: string;
  competitors?: string;
  industry?: string;
  website?: string;
  linkedin_url?: string;
  company_type?: string;
  created_at?: string;
  funding_details?: string;
  founded_year?: string;
}

// This generic type creates a new interface that extends the provided type T and adds a property [key: string]: any.
// [key: string]: any allows for the addition of arbitrary properties with string keys and any value type.
// Used to add custom column rows to the table.
type Extendable<T> = T & Record<string, any>; 

export interface AccountTableRow extends Extendable<BaseAccountTableRow> {};

export const accountColumns: ColumnDef<AccountTableRow>[] = [
  {
    id: "select",
    header: ({table}: {table: Table<AccountTableRow> }) => (
      <Checkbox
        className="bg-white data-[state=checked]:bg-purple-400"
        checked={
          table.getIsAllPageRowsSelected() ||
          (table.getIsSomePageRowsSelected() && "indeterminate")
        }
        onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
        aria-label="Select all"
      />
    ),
    cell: ({ row }) => (
      <Checkbox
        className="data-[state=checked]:bg-purple-400"
        checked={row.getIsSelected()}
        onCheckedChange={(value) => row.toggleSelected(!!value)}
        aria-label="Select row"
      />
    ),
    size: 50,
    enableSorting: false,
    enableHiding: false,
    meta: {
      displayName: "",
      visibleInitially: true,
    } as CustomColumnMeta,
  },
  {
    accessorKey: "name",
    header: ({ column }) => {
      return (
        <div className="flex justify-between items-center gap-2 mr-2">
          Name
          <SortingDropdown
            onSelect={(val) => {
              if (val === "asc") {
                column.toggleSorting(false);
              } else if (val === "desc") {
                column.toggleSorting(true);
              } else if (val === "none") {
                column.clearSorting();
              }
            }}
          >
            <ChevronsUpDown size={18} />
          </SortingDropdown>
        </div>
      );
    },
    size: 100,
    meta: {
      displayName: "Name",
      visibleInitially: true,
    } as CustomColumnMeta,
  },
  {
    accessorKey: "status",
    header: "Status",
    size: 100,
    // Reference: https://tanstack.com/table/v8/docs/guide/column-filtering.
    filterFn: "arrIncludesSome",
    meta: {
      displayName: "Status",
      visibleInitially: true,
    } as CustomColumnMeta,
  },
  {
    accessorKey: "location",
    header: "HQ",
    size: 100,
    meta: {
      displayName: "HQ",
      visibleInitially: false,
    } as CustomColumnMeta,
  },
  {
    accessorKey: "employee_count",
    header: "Employee Count",
    size: 100,
    meta: {
      displayName: "Employee Count",
      visibleInitially: true,
    } as CustomColumnMeta,
  },
  {
    accessorKey: "customers",
    header: "Customers",
    size: 200,
    meta: {
      displayName: "Customers",
      visibleInitially: true,
    } as CustomColumnMeta,
  },
  {
    accessorKey: "technologies",
    header: "Technologies",
    size: 200,
    meta: {
      displayName: "Technologies",
      visibleInitially: true,
    } as CustomColumnMeta,
  },
  {
    accessorKey: "competitors",
    header: "Competitors",
    size: 200,
    meta: {
      displayName: "Competitors",
      visibleInitially: true,
    } as CustomColumnMeta,
  },
  {
    accessorKey: "industry",
    header: "Industry",
    size: 200,
    meta: {
      displayName: "Industry",
      visibleInitially: true,
    } as CustomColumnMeta,
  },
  {
    accessorKey: "website",
    header: "Website",
    size: 100,
    meta: {
      displayName: "Website",
      visibleInitially: false,
    } as CustomColumnMeta,
  },
  {
    accessorKey: "linkedin_url",
    header: "LinkedIn URL",
    size: 100,
    cell: ({ row }) => {
      const url: string|undefined = row.getValue("linkedin_url");
      if (!url) {
        return <div></div>;
      }
      return (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 text-blue-600 hover:text-blue-900 hover:underline"
        >
          {url} <ExternalLink size={18} />
        </a>
      );
    },
    meta: {
      displayName: "LinkedIn URL",
      visibleInitially: false,
    } as CustomColumnMeta,
  },
  {
    accessorKey: "company_type",
    header: "Company Type",
    size: 100,
    meta: {
      displayName: "Company Type",
      visibleInitially: false,
    } as CustomColumnMeta,
  },
  {
    accessorKey: "created_at",
    header: "Created On",
    size: 100,
    meta: {
      displayName: "Created On",
      visibleInitially: false,
    } as CustomColumnMeta,
  },
  {
    accessorKey: "funding_details",
    header: "Funding Details",
    size: 100,
    meta: {
      displayName: "Funding Details",
      visibleInitially: false,
    } as CustomColumnMeta,
  },
  {
    accessorKey: "founded_year",
    header: "Founded Year",
    size: 100,
    meta: {
      displayName: "Founded Year",
      visibleInitially: false,
    } as CustomColumnMeta,
  },
];
