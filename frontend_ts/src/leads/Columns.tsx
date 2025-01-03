import { ChevronsUpDown, ExternalLink } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import SortingDropdown from "../table/SortingDropdown";
import { ReactNode } from "react";
import { CustomColumnMeta } from "@/table/CustomColumnMeta";
import { ColumnDef, Table } from "@tanstack/react-table";

interface BaseLeadTableRow {
  id: string;
  select?: ReactNode;
  name: string;
  linkedin_url: string;
  status: string;
  company_name: string;
  role_title: string;
  duration_at_company: string;
  email: string;
  phone: string;
  created_at?: string;
  linkedin_activity_status?: string;
}

// This generic type creates a new interface that extends the provided type T and adds a property [key: string]: any.
// [key: string]: any allows for the addition of arbitrary properties with string keys and any value type.
// Used to add custom column rows to the table.
type Extendable<T> = T & Record<string, any>; 

export interface LeadTableRow extends Extendable<BaseLeadTableRow>{};

// Columns used by Leads Table.
export const leadsColumns: ColumnDef<LeadTableRow>[] = [
  {
    id: "select",
    header: ({table}: {table: Table<LeadTableRow> })  => (
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
    } as CustomColumnMeta
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
    } as CustomColumnMeta
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
      visibleInitially: true,
    } as CustomColumnMeta
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
    } as CustomColumnMeta
  },
  {
    accessorKey: "company_name",
    header: "Company Name",
    size: 100,
    meta: {
      displayName: "Company Name",
      visibleInitially: true,
    } as CustomColumnMeta
  },
  {
    accessorKey: "role_title",
    header: "Role Title",
    size: 100,
    meta: {
      displayName: "Role Title",
      visibleInitially: true,
    } as CustomColumnMeta
  },
  {
    accessorKey: "duration_at_company",
    header: "Duration at Company",
    size: 100,
    meta: {
      displayName: "Duration at Company",
      visibleInitially: true,
    } as CustomColumnMeta
  },
  {
    accessorKey: "email",
    header: "Email",
    size: 100,
    meta: {
      displayName: "Email",
      visibleInitially: false,
    } as CustomColumnMeta
  },
  {
    accessorKey: "phone",
    header: "Phone Number",
    size: 100,
    meta: {
      displayName: "Phone Number",
      visibleInitially: false,
    } as CustomColumnMeta
  },
  {
    accessorKey: "created_at",
    header: "Created On",
    size: 100,
    meta: {
      displayName: "Created On",
      visibleInitially: false,
    } as CustomColumnMeta
  },
  {
    accessorKey: "linkedin_activity_status",
    header: "LinkedIn Activity Enrichment Status",
    size: 100,
    meta: {
      displayName: "LinkedIn Activity Enrichment Status",
      visibleInitially: false,
    } as CustomColumnMeta
  },
];
