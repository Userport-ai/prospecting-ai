import { ChevronsUpDown, ExternalLink } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import SortingDropdown from "../table/SortingDropdown";
import { ColumnDef, Table } from "@tanstack/react-table";
import { CustomColumnMeta } from "@/table/CustomColumnMeta";
import { Account as AccountRow } from "@/services/Accounts";
import { formatDate } from "@/common/utils";
import { getCustomColumnDisplayName } from "@/table/AddCustomColumn";

// Base Account Columns that we know will exist in the table and are statically defined.
const baseAccountColumns: ColumnDef<AccountRow>[] = [
  {
    // Allows user to select rows from the table.
    id: "select",
    header: ({ table }: { table: Table<AccountRow> }) => (
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
    cell: (info) => (
      <Checkbox
        className="data-[state=checked]:bg-purple-400"
        checked={info.row.getIsSelected()}
        onCheckedChange={(value) => info.row.toggleSelected(!!value)}
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
    id: "name",
    accessorFn: (row) => row.name,
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
    id: "enrichment_status",
    accessorFn: (row) => row.enrichment_status,
    header: "Enrichment Status",
    size: 100,
    // Reference: https://tanstack.com/table/v8/docs/guide/column-filtering.
    filterFn: "arrIncludesSome",
    meta: {
      displayName: "Enrichment Status",
      visibleInitially: true,
    } as CustomColumnMeta,
  },
  {
    id: "location",
    accessorFn: (row) => row.location,
    header: "HQ",
    size: 100,
    meta: {
      displayName: "HQ",
      visibleInitially: false,
    } as CustomColumnMeta,
  },
  {
    id: "employee_count",
    accessorFn: (row) => row.employee_count,
    header: "Employee Count",
    size: 100,
    meta: {
      displayName: "Employee Count",
      visibleInitially: true,
    } as CustomColumnMeta,
  },
  {
    id: "customers",
    accessorFn: (row) => row.customers,
    header: "Customers",
    size: 200,
    meta: {
      displayName: "Customers",
      visibleInitially: true,
    } as CustomColumnMeta,
  },
  {
    id: "technologies",
    accessorFn: (row) => row.technologies,
    header: "Technologies",
    cell: (info) => {
      if (info.getValue()) {
        return JSON.stringify(info.getValue());
      }
      return null;
    },
    size: 300,
    meta: {
      displayName: "Technologies",
      visibleInitially: true,
    } as CustomColumnMeta,
  },
  {
    id: "competitors",
    accessorFn: (row) => row.competitors,
    header: "Competitors",
    size: 200,
    meta: {
      displayName: "Competitors",
      visibleInitially: true,
    } as CustomColumnMeta,
  },
  {
    id: "industry",
    accessorFn: (row) => row.industry,
    header: "Industry",
    size: 200,
    meta: {
      displayName: "Industry",
      visibleInitially: true,
    } as CustomColumnMeta,
  },
  {
    id: "website",
    accessorFn: (row) => row.website,
    header: "Website",
    cell: (info) => {
      const url = info.getValue() as string | null;
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
    size: 100,
    meta: {
      displayName: "Website",
      visibleInitially: false,
    } as CustomColumnMeta,
  },
  {
    id: "linkedin_url",
    accessorFn: (row) => row.linkedin_url,
    header: "LinkedIn URL",
    size: 100,
    cell: (info) => {
      const url = info.getValue() as string | null;
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
    id: "company_type",
    accessorFn: (row) => row.company_type,
    header: "Company Type",
    size: 100,
    meta: {
      displayName: "Company Type",
      visibleInitially: false,
    } as CustomColumnMeta,
  },
  {
    id: "created_at",
    accessorFn: (row) => formatDate(row.created_at),
    header: "Created On",
    size: 200,
    meta: {
      displayName: "Created On",
      visibleInitially: false,
    } as CustomColumnMeta,
  },
  {
    id: "funding_details",
    accessorFn: (row) => row.funding_details,
    header: "Funding Details",
    cell: (info) => {
      if (info.getValue()) {
        return JSON.stringify(info.getValue());
      }
      return null;
    },
    size: 100,
    meta: {
      displayName: "Funding Details",
      visibleInitially: false,
    } as CustomColumnMeta,
  },
  {
    id: "founded_year",
    accessorFn: (row) => row.founded_year,
    header: "Founded Year",
    size: 100,
    meta: {
      displayName: "Founded Year",
      visibleInitially: false,
    } as CustomColumnMeta,
  },
  {
    id: "enrichment_sources",
    accessorFn: (row) => row.enrichment_sources,
    header: "Enrichment Sources",
    cell: (info) => {
      if (info.getValue()) {
        return JSON.stringify(info.getValue());
      }
      return null;
    },
    size: 100,
    meta: {
      displayName: "Enrichment Sources",
      visibleInitially: false,
    } as CustomColumnMeta,
  },
  {
    id: "last_enriched_at",
    accessorFn: (row) =>
      row.last_enriched_at ? formatDate(row.last_enriched_at) : "Unknown",
    header: "Last Enriched At",
    size: 100,
    meta: {
      displayName: "Last Enriched At",
      visibleInitially: false,
    } as CustomColumnMeta,
  },
];

// Fetches the final Column definition for the given set of rows
// by adding Custom Columns to base static column definition using
// information from the given Account Rows.
export const getAccountColumns = (
  rows: AccountRow[]
): ColumnDef<AccountRow>[] => {
  // Get custom columns.
  var customColumnKeys = new Set<string>();
  for (const row of rows) {
    if (!row.custom_fields) {
      continue;
    }
    const customFields: string[] = Object.keys(row.custom_fields);
    customFields.forEach((cf) => customColumnKeys.add(cf));
  }

  var finalColumns: ColumnDef<AccountRow>[] = [...baseAccountColumns];
  customColumnKeys.forEach((columnKey) => {
    finalColumns.push({
      id: columnKey,
      accessorFn: (row) => row.custom_fields,
      header: getCustomColumnDisplayName(columnKey),
      cell: (info) => {
        const customFields = info.getValue() as Record<string, any> | null;
        if (customFields && columnKey in customFields) {
          // Return value of the custom fiel.
          return customFields[columnKey];
        }
        return null;
      },
      size: 100,
      filterFn: "arrIncludesSome",
      meta: {
        displayName: getCustomColumnDisplayName(columnKey),
        visibleInitially: true,
      },
    });
  });
  return finalColumns;
};
