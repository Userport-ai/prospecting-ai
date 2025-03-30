import { ChevronsUpDown, Link } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import SortingDropdown from "../table/SortingDropdown";
import { CustomColumnMeta } from "@/table/CustomColumnMeta";
import { ColumnDef, Table } from "@tanstack/react-table";
import { Lead as LeadRow } from "@/services/Leads";
import { formatDate } from "@/common/utils";
import { getCustomColumnDisplayName } from "@/table/AddCustomColumn";
import CellListView from "@/table/CellListView";
import { CustomColumnValueData } from "@/services/CustomColumn";
import CustomColumnValueRender from "@/table/CustomColumnValueRender";

// Base Lead Columns that we know will exist in the table and are statically defined.
export const baseLeadColumns: ColumnDef<LeadRow>[] = [
  {
    id: "select",
    maxSize: 50,
    header: ({ table }: { table: Table<LeadRow> }) => (
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
    enableSorting: false,
    enableHiding: false,
    meta: {
      displayName: "",
      visibleInitially: true,
    } as CustomColumnMeta,
  },
  {
    id: "name",
    minSize: 200,
    accessorFn: (row) => `${row.first_name} ${row.last_name}`,
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
    meta: {
      displayName: "Name",
      visibleInitially: true,
    } as CustomColumnMeta,
  },
  {
    id: "linkedin_url",
    accessorFn: (row) => row.linkedin_url,
    header: "LinkedIn URL",
    size: 20,
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
    id: "enrichment_status",
    accessorFn: (row) => row.enrichment_status,
    size: 50,
    header: "Enrichment Status",
    // Reference: https://tanstack.com/table/v8/docs/guide/column-filtering.
    filterFn: "arrIncludesSome",
    meta: {
      displayName: "Enrichment Status",
      visibleInitially: false,
    } as CustomColumnMeta,
  },
  {
    id: "company_name",
    accessorFn: (row) => row.account_details.name,
    minSize: 200,
    header: "Company Name",
    meta: {
      displayName: "Company Name",
      visibleInitially: true,
    } as CustomColumnMeta,
  },
  {
    id: "role_title",
    minSize: 200,
    accessorFn: (row) => row.role_title,
    header: "Role Title",
    meta: {
      displayName: "Role Title",
      visibleInitially: true,
    } as CustomColumnMeta,
  },
  {
    id: "email",
    minSize: 200,
    accessorFn: (row) => row.email,
    header: "Email",
    meta: {
      displayName: "Email",
      visibleInitially: false,
    } as CustomColumnMeta,
  },
  {
    id: "phone",
    accessorFn: (row) => row.phone,
    header: "Phone Number",
    meta: {
      displayName: "Phone Number",
      visibleInitially: false,
    } as CustomColumnMeta,
  },
  {
    id: "created_at",
    accessorFn: (row) => formatDate(row.created_at),
    header: "Created On",
    meta: {
      displayName: "Created On",
      visibleInitially: false,
    } as CustomColumnMeta,
  },
];

// Fetches the final Column definition for the given set of rows
// by adding Custom Columns to base static column definition using
// information from the given Lead Rows.
export const getLeadColumns = (rows: LeadRow[]): ColumnDef<LeadRow>[] => {
  // Get custom columns from all the rows in table.
  var customFieldKeys = new Set<string>();
  for (const row of rows) {
    if (!row.custom_fields) {
      continue;
    }
    const customFields: string[] = Object.keys(row.custom_fields);
    customFields.forEach((cf) => customFieldKeys.add(cf));
  }

  var finalColumns: ColumnDef<LeadRow>[] = [...baseLeadColumns];
  // Custom columns also has AI created fields like "evaluation" which are
  // populated whenever the lead is suggested or approved by the user.
  // Since we know the structure of this object, we will derive columns
  // from its keys separately.
  const evaluationKey = "evaluation";
  if (customFieldKeys.has(evaluationKey)) {
    const evaluationColumns: ColumnDef<LeadRow>[] = [
      {
        id: "fit_score",
        header: "Fit Score",
        size: 20,
        accessorFn: (row) => row.score,
        meta: {
          displayName: "Fit Score",
          visibleInitially: true,
        } as CustomColumnMeta,
      },
      {
        id: "persona_match",
        header: "Persona Match",
        size: 50,
        filterFn: "arrIncludesSome",
        accessorFn: (row) => {
          if (
            row.custom_fields &&
            row.custom_fields.evaluation &&
            row.custom_fields.evaluation.persona_match &&
            row.custom_fields.evaluation.persona_match !== "null" // LLM can mark a persona as "null" sometimes, sigh.
          ) {
            return row.custom_fields.evaluation.persona_match;
          }
          return "unknown";
        },
        cell: (info) => {
          const personaMatchValue = info.getValue() as string;
          return getCustomColumnDisplayName(personaMatchValue);
        },
        meta: {
          displayName: "Persona Match",
          visibleInitially: true,
        } as CustomColumnMeta,
      },
      {
        id: "matching_signals",
        header: "Matching Signals",
        minSize: 600,
        accessorFn: (row: LeadRow) => {
          if (!row.custom_fields || !row.custom_fields.evaluation) {
            return null;
          }
          const matchingCriteria =
            row.custom_fields.evaluation.matching_criteria;
          const matchingSignals = row.custom_fields.evaluation.matching_signals;
          if (matchingSignals) {
            return matchingSignals;
          } else if (matchingCriteria) {
            return matchingCriteria;
          }
          return null;
        },
        cell: (info) => {
          const matchingSignals = info.getValue() as string[] | null;
          if (!matchingSignals) {
            return null;
          }
          return <CellListView values={matchingSignals} />;
        },
        meta: {
          displayName: "Matching Signals",
          visibleInitially: true,
          cellExpandable: true,
        } as CustomColumnMeta,
      },
      {
        id: "rationale",
        header: "Rationale",
        minSize: 400,
        accessorFn: (row) =>
          row.custom_fields ? row.custom_fields.evaluation.rationale : null,
        meta: {
          displayName: "Rationale",
          visibleInitially: true,
          cellExpandable: true,
        } as CustomColumnMeta,
      },
    ];
    finalColumns.push(...evaluationColumns);
  }

  // Get unique custom column definitions from the rows provided.
  // This is different from custom field values which are not user defined.
  const customColumnDefinitions = new Map<string, CustomColumnValueData>();

  for (const row of rows) {
    if (row.custom_column_values) {
      for (const columnId in row.custom_column_values) {
        if (!customColumnDefinitions.has(columnId)) {
          // Store the metadata (name, type etc.) from the first row we see it in
          customColumnDefinitions.set(
            columnId,
            row.custom_column_values[columnId]
          );
        }
      }
    }
  }

  // Add definitions for each unique custom column found
  customColumnDefinitions.forEach((colData, columnId) => {
    finalColumns.push({
      id: columnId, // Use the UUID as the column ID
      header: colData.name, // Use the name from the custom column data
      accessorFn: (row) => row.custom_column_values?.[columnId]?.value ?? null, // Access the specific value
      cell: (info) => {
        const columnId = info.column.id;
        const customColumnMap = info.row.original.custom_column_values;
        const customColumnValueData = customColumnMap?.[columnId];

        return (
          <CustomColumnValueRender
            customColumnValueData={customColumnValueData}
          />
        );
      },
      minSize: 150,
      enableSorting: false,
      enableColumnFilter: false,
      meta: {
        displayName: colData.name,
        visibleInitially: true,
        cellExpandable:
          ["string", "json_object", "enum"].includes(colData.response_type) &&
          colData.rationale !== null,
      } as CustomColumnMeta,
    });
  });
  return finalColumns;
};
