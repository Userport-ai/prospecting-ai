// Import CustomColumnValueData directly from its source
import {
  CustomColumn,
  CustomColumnValueData,
  getCustomColumn,
} from "@/services/CustomColumn";
import { ChevronsUpDown, Link, Loader2, Pencil } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import SortingDropdown from "../table/SortingDropdown";
import { ColumnDef, Table } from "@tanstack/react-table";
import { CustomColumnMeta } from "@/table/CustomColumnMeta";
import { Account as AccountRow, FundingDetails } from "@/services/Accounts";
import { formatDate } from "@/common/utils";
import { EnrichmentStatus, RecentCompanyEvent } from "@/services/Common";
import FundingDetailsView from "./FundingDetailsView";
import CellListView from "../table/CellListView";
import { cn } from "@/lib/utils";
import { wrapColumnContentClass } from "@/common/utils";
import EnrichmentStatusView from "./EnrichmentStatusView";
import RecentCompanyEventsView from "./RecentCompanyEventsView";
import CustomColumnValueRender from "@/table/CustomColumnValueRender";
import { useAuthContext } from "@/auth/AuthProvider";
import { useToast } from "@/hooks/use-toast";
import { useState } from "react";

const EditCustomColumnBtn: React.FC<{
  columnId: string;
  onCustomColumnFetch: (customColumn: CustomColumn) => void;
}> = ({ columnId, onCustomColumnFetch }) => {
  const authContext = useAuthContext();
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);

  const handleClick = async () => {
    setLoading(true);
    try {
      const customColumn = await getCustomColumn(authContext, columnId);
      onCustomColumnFetch(customColumn);
    } catch (error) {
      console.error(
        `Failed to fetch custom column with ID: ${columnId} lead generation with error: ${error}`
      );
      // Show toast.
      toast({
        variant: "destructive",
        title: "Uh oh! Something went wrong.",
        description: "Could not Edit Ask AI column, please contact support!",
      });
    } finally {
      setLoading(false);
    }
  };

  return loading ? (
    <Loader2 className="h-4 w-4 mr-2 animate-spin text-purple-400" />
  ) : (
    <Pencil
      className="hover:cursor-pointer hover:text-yellow-300"
      onClick={handleClick}
      size={16}
    />
  );
};

// Base Account Columns that we know will exist in the table and are statically defined.
const getBaseAccountColumns = (
  onRefreshTable?: () => void
): ColumnDef<AccountRow>[] => {
  return [
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
      minSize: 80,
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
      minSize: 200,
      cell: (info) => {
        const enrichmentStatus = info.getValue() as EnrichmentStatus | null;
        if (!enrichmentStatus) {
          return null;
        }

        return (
          <EnrichmentStatusView
            accountId={info.row.original.id}
            enrichmentStatus={enrichmentStatus}
            onLeadGenTriggered={() => {
              if (onRefreshTable) onRefreshTable();
            }}
          />
        );
      },
      // Reference: https://tanstack.com/table/v8/docs/guide/column-filtering.
      filterFn: "arrIncludesSome",
      meta: {
        displayName: "Enrichment Status",
        visibleInitially: true,
      } as CustomColumnMeta,
    },
    {
      id: "employee_count",
      accessorFn: (row) => row.employee_count,
      header: "Employee Count",
      minSize: 100,
      maxSize: 100,
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
      id: "location",
      accessorFn: (row) => row.location,
      header: "HQ",
      minSize: 100,
      maxSize: 100,
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
  ];
};

// Secondary Account columns we know will exist in the table but we want them to be at the end
// relative to custom columns.
const secondaryAccountColumns: ColumnDef<AccountRow>[] = [
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
    id: "recent_events",
    header: "Recent Events",
    accessorFn: (row) => {
      if (!row.recent_events || row.recent_events.length == 0) {
        return null;
      }
      return row.recent_events;
    },
    minSize: 200,
    maxSize: 200,
    cell: (info) => {
      const recentEvents = info.getValue() as RecentCompanyEvent[] | null;
      if (!recentEvents) {
        return null;
      }
      return <RecentCompanyEventsView recentEvents={recentEvents} />;
    },
    meta: {
      displayName: "Recent Events",
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
    minSize: 80,
    maxSize: 80,
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
          <Link size={18} />
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
    minSize: 80,
    maxSize: 80,
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
          <Link size={18} />
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
    minSize: 120,
    maxSize: 120,
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
    minSize: 200,
    maxSize: 200,
    cell: (info) => {
      const fundingDetails = info.getValue() as FundingDetails | null;
      if (!fundingDetails) {
        return null;
      }
      return <FundingDetailsView fundingDetails={fundingDetails} />;
    },
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
    minSize: 80,
    maxSize: 80,
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
  {
    id: "created_at",
    accessorFn: (row) => formatDate(row.created_at),
    header: "Created On",
    size: 50,
    cell: (info) => {
      const dateStr = info.getValue() as string;
      return <p className="text-xs">{dateStr}</p>;
    },
    meta: {
      displayName: "Created On",
      visibleInitially: true,
    } as CustomColumnMeta,
  },
];

export const getAccountColumns = (
  rows: AccountRow[],
  onRefreshTable: () => void,
  onCustomColumnEditRequest: (customColumn: CustomColumn) => void
): ColumnDef<AccountRow>[] => {
  const finalColumns: ColumnDef<AccountRow>[] = [
    ...getBaseAccountColumns(onRefreshTable),
  ];

  // Get unique custom column definitions from the rows provided
  var customColumnDefinitions = new Map<string, CustomColumnValueData>();

  for (const row of rows) {
    if (row.custom_column_values) {
      for (const columnId in row.custom_column_values) {
        if (!customColumnDefinitions.has(columnId)) {
          // Store the metadata (name, type etc.) from the first row we see it in
          // Make sure to include the columnId in the data
          const columnData = {
            ...row.custom_column_values[columnId],
            columnId: columnId, // Explicitly add the columnId
          };
          customColumnDefinitions.set(columnId, columnData);
        }
      }
    }
  }

  // Helper method that returns true if the custom column name contains "Fit" and false otherwise.
  const columnNameIncludesFit = (colData: CustomColumnValueData): boolean => {
    return colData.name.includes("Fit");
  };

  // Sort custom columns if Fit Score is present so it is always the first custom column.
  var fitScoreColumEntry: [string, CustomColumnValueData] | null = null;
  customColumnDefinitions.forEach((colData, columnId) => {
    if (columnNameIncludesFit(colData)) {
      // Fit Score column found.
      fitScoreColumEntry = [columnId, colData];
    }
  });
  if (fitScoreColumEntry) {
    // This should be the first column.
    var sortedCustomColumnDefinitions = new Map<
      string,
      CustomColumnValueData
    >();
    sortedCustomColumnDefinitions.set(
      fitScoreColumEntry[0],
      fitScoreColumEntry[1]
    );
    customColumnDefinitions.forEach((colData, columnId) => {
      if (columnId !== fitScoreColumEntry![0]) {
        sortedCustomColumnDefinitions.set(columnId, colData);
      }
    });
    customColumnDefinitions = sortedCustomColumnDefinitions;
  }

  // Add definitions for each unique custom column found
  customColumnDefinitions.forEach((colData, columnId) => {
    finalColumns.push({
      id: columnId, // Use the UUID as the column ID
      header: ({ column }) => {
        return (
          <div className="flex w-full justify-between items-center">
            {colData.name}
            <div className="flex gap-2">
              {/* Only make Score custom column sortable */}
              {columnNameIncludesFit(colData) && (
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
              )}

              {/* Button to edit the custom column. */}
              <EditCustomColumnBtn
                columnId={columnId}
                onCustomColumnFetch={onCustomColumnEditRequest}
              />
            </div>
          </div>
        );
      },
      accessorFn: (row) => row.custom_column_values?.[columnId]?.value ?? null, // Access the specific value
      cell: (info) => {
        const columnId = info.column.id;
        const accountId = info.row.original.id; // Get the account ID
        const customColumnMap = info.row.original.custom_column_values;
        const customColumnValueData = customColumnMap?.[columnId];

        // Ensure columnId is included in the data passed to the component
        const enrichedColumnData = customColumnValueData
          ? {
              ...customColumnValueData,
              columnId: columnId,
            }
          : null;

        return (
          <CustomColumnValueRender
            customColumnValueData={enrichedColumnData}
            entityId={accountId}
            onValueGenerated={onRefreshTable}
            disableGeneration={
              info.row.original.enrichment_status.avg_completion_percent !== 100
            }
          />
        );
      },
      minSize: !columnNameIncludesFit(colData) ? 300 : 200, // Hacky way to have smaller width for Account Fit Score column. TODO: Store this in backend config instead.
      maxSize: !columnNameIncludesFit(colData) ? 300 : 200, // Hacky way to have smaller width for Account Fit Score column. TODO: Store this in backend config instead.
      enableSorting: !columnNameIncludesFit(colData) ? false : true,
      enableColumnFilter: false,
      meta: {
        displayName: colData.name,
        visibleInitially: true,
        cellExpandable: ["string", "json_object", "enum"].includes(
          colData.response_type
        ),
        isCustomColumn: true,
      } as CustomColumnMeta,
    });
  });

  return [...finalColumns, ...secondaryAccountColumns];
};
