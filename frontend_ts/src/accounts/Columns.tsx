import { ChevronsUpDown } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import SortingDropdown from "../table/SortingDropdown";
import { ColumnDef, Table } from "@tanstack/react-table";
import { CustomColumnMeta } from "@/table/CustomColumnMeta";
import { Account as AccountRow, FundingDetails } from "@/services/Accounts";
import { formatDate } from "@/common/utils";
import { getCustomColumnDisplayName } from "@/table/AddCustomColumn";
import { Link } from "react-router";
import { EnrichmentStatus } from "@/services/Common";
import { Progress } from "@/components/ui/progress";
import FundingDetailsView from "./FundingDetailsView";
import CellListView from "../table/CellListView";
import { cn } from "@/lib/utils";
import { wrapColumnContentClass } from "@/common/utils";

// Base Account Columns that we know will exist in the table and are statically defined.
const baseAccountColumns: ColumnDef<AccountRow>[] = [
  {
    // Allows user to select rows from the table.
    id: "select",
    maxSize: 50,
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
    minSize: 100,
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
    cell: (info) => {
      const name = info.getValue() as string | null;
      if (!name) {
        return null;
      }
      return <p className={wrapColumnContentClass}>{name}</p>;
    },
    meta: {
      displayName: "Name",
      visibleInitially: true,
    } as CustomColumnMeta,
  },
  {
    id: "enrichment_status",
    accessorFn: (row) => row.enrichment_status,
    header: "Enrichment Status",
    cell: (info) => {
      const enrichmentStatus = info.getValue() as EnrichmentStatus | null;
      if (enrichmentStatus) {
        if (enrichmentStatus.total_enrichments === 0) {
          // Enrichment scheduled.
          return <p className="text-red-950 font-medium">Scheduled</p>;
        } else if (
          enrichmentStatus.total_enrichments === enrichmentStatus.completed
        ) {
          // Enrichment complete, link to Leads table on click.
          const accountId = info.row.original.id;
          const url = `/accounts/${accountId}/leads`;
          return (
            <Link to={url} className="text-blue-500 underline font-medium">
              Complete
            </Link>
          );
        } else if (enrichmentStatus.failed > 0) {
          return <p className="text-red-700 font-medium">Failed</p>;
        } else {
          return (
            <div>
              <p className="text-yellow-600 font-medium">In Progress</p>
              <Progress
                value={
                  (enrichmentStatus.completed /
                    enrichmentStatus.total_enrichments) *
                  100
                }
              />
            </div>
          );
        }
      }
      return null;
    },
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
    minSize: 200,
    cell: (info) => {
      const hq = info.getValue() as string | null;
      if (!hq) {
        return null;
      }
      return <p className="whitespace-normal break-words">{hq}</p>;
    },
    meta: {
      displayName: "HQ",
      visibleInitially: true,
    } as CustomColumnMeta,
  },
  {
    id: "employee_count",
    accessorFn: (row) => row.employee_count,
    header: "Employee Count",
    size: 20,
    cell: (info) => {
      const count = info.getValue() as number | null;
      if (!count) {
        return null;
      }
      return <p className={wrapColumnContentClass}>{count}</p>;
    },
    meta: {
      displayName: "Employee Count",
      visibleInitially: true,
    } as CustomColumnMeta,
  },
  {
    id: "customers",
    accessorFn: (row) => {
      if (!row.customers || row.customers.length == 0) {
        return null;
      }
      return row.customers;
    },
    header: "Customers",
    minSize: 200,
    cell: (info) => {
      const customers = info.getValue() as string[] | null;
      if (!customers) {
        return null;
      }
      return <CellListView values={customers} />;
    },
    meta: {
      displayName: "Customers",
      visibleInitially: true,
      cellExpandable: true,
    } as CustomColumnMeta,
  },
  {
    id: "technologies",
    accessorFn: (row) => {
      if (!row.technologies || row.technologies.length == 0) {
        return null;
      }
      return row.technologies;
    },
    header: "Technologies",
    minSize: 200,
    cell: (info) => {
      const technologies = info.getValue() as string[] | null;
      if (!technologies) {
        return null;
      }
      return <CellListView values={technologies} />;
    },
    meta: {
      displayName: "Technologies",
      visibleInitially: true,
      cellExpandable: true,
    } as CustomColumnMeta,
  },
  {
    id: "competitors",
    accessorFn: (row) => {
      if (!row.competitors || row.competitors.length == 0) {
        return null;
      }
      return row.competitors;
    },
    header: "Competitors",
    minSize: 200,
    cell: (info) => {
      const competitors = info.getValue() as string[] | null;
      if (!competitors) {
        return null;
      }
      return <CellListView values={competitors} />;
    },
    meta: {
      displayName: "Competitors",
      visibleInitially: true,
      cellExpandable: true,
    } as CustomColumnMeta,
  },
  {
    id: "industry",
    accessorFn: (row) => row.industry,
    header: "Industry",
    minSize: 100,
    cell: (info) => {
      const industry = info.getValue() as string | null;
      if (!industry) {
        return null;
      }
      return <p className={wrapColumnContentClass}>{industry}</p>;
    },
    meta: {
      displayName: "Industry",
      visibleInitially: true,
    } as CustomColumnMeta,
  },
  {
    id: "website",
    accessorFn: (row) => row.website,
    header: "Website",
    minSize: 200,
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
          className={cn(
            "flex items-center gap-1 text-blue-600 hover:text-blue-900 hover:underline",
            wrapColumnContentClass
          )}
        >
          {url}
        </a>
      );
    },
    meta: {
      displayName: "Website",
      visibleInitially: true,
    } as CustomColumnMeta,
  },
  {
    id: "linkedin_url",
    accessorFn: (row) => row.linkedin_url,
    header: "LinkedIn URL",
    minSize: 300,
    cell: (info) => {
      const url = info.getValue() as string | null;
      if (!url) {
        return null;
      }
      return (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className={cn(
            "flex items-center gap-1 text-blue-600 hover:text-blue-900 hover:underline",
            wrapColumnContentClass
          )}
        >
          {url}
        </a>
      );
    },
    meta: {
      displayName: "LinkedIn URL",
      visibleInitially: true,
    } as CustomColumnMeta,
  },
  {
    id: "company_type",
    accessorFn: (row) => row.company_type,
    header: "Company Type",
    size: 20,
    cell: (info) => {
      const type = info.getValue() as string | null;
      if (!type) {
        return null;
      }
      return <p className={wrapColumnContentClass}>{type}</p>;
    },
    meta: {
      displayName: "Company Type",
      visibleInitially: true,
    } as CustomColumnMeta,
  },
  {
    id: "created_at",
    accessorFn: (row) => formatDate(row.created_at),
    header: "Created On",
    meta: {
      displayName: "Created On",
      visibleInitially: true,
    } as CustomColumnMeta,
  },
  {
    id: "funding_details",
    accessorFn: (row) => {
      if (
        !row.funding_details ||
        Object.keys(row.funding_details).length === 0
      ) {
        return null;
      }
      return row.funding_details;
    },
    header: "Funding Details",
    minSize: 250,
    cell: (info) => {
      const fundingDetails = info.getValue() as FundingDetails | null;
      if (!fundingDetails) {
        return null;
      }
      return <FundingDetailsView fundingDetails={fundingDetails} />;
    },
    size: 100,
    meta: {
      displayName: "Funding Details",
      visibleInitially: true,
      cellExpandable: true,
    } as CustomColumnMeta,
  },
  {
    id: "founded_year",
    accessorFn: (row) => row.founded_year,
    header: "Founded Year",
    size: 20,
    cell: (info) => {
      const founded_year = info.getValue() as string | null;
      if (!founded_year) {
        return null;
      }
      return <p className={wrapColumnContentClass}>{founded_year}</p>;
    },
    meta: {
      displayName: "Founded Year",
      visibleInitially: true,
    } as CustomColumnMeta,
  },
  {
    id: "last_enriched_at",
    accessorFn: (row) =>
      row.last_enriched_at ? formatDate(row.last_enriched_at) : "Unknown",
    header: "Last Enriched At",
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
