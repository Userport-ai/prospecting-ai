import { ChevronsUpDown, ExternalLink } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import SortingDropdown from "../table/SortingDropdown";
import { CustomColumnMeta } from "@/table/CustomColumnMeta";
import { ColumnDef, Table } from "@tanstack/react-table";
import { Lead as LeadRow } from "@/services/Leads";
import { formatDate } from "@/common/utils";
import { getCustomColumnDisplayName } from "@/table/AddCustomColumn";

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
    minSize: 200,
    accessorFn: (row) => row.linkedin_url,
    header: "LinkedIn URL",
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
      visibleInitially: true,
    } as CustomColumnMeta,
  },
  {
    id: "enrichment_status",
    accessorFn: (row) => row.enrichment_status,
    header: "Enrichment Status",
    // Reference: https://tanstack.com/table/v8/docs/guide/column-filtering.
    filterFn: "arrIncludesSome",
    meta: {
      displayName: "Enrichment Status",
      visibleInitially: true,
    } as CustomColumnMeta,
  },
  {
    id: "company_name",
    minSize: 200,
    accessorFn: (row) => row.account_details.name,
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
    id: "duration_at_company",
    header: "Duration at Company",
    meta: {
      displayName: "Duration at Company",
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
  {
    id: "linkedin_activity_status",
    header: "LinkedIn Activity Enrichment Status",
    meta: {
      displayName: "LinkedIn Activity Enrichment Status",
      visibleInitially: false,
    } as CustomColumnMeta,
  },
];

// Fetches the final Column definition for the given set of rows
// by adding Custom Columns to base static column definition using
// information from the given Lead Rows.
export const getLeadColumns = (rows: LeadRow[]): ColumnDef<LeadRow>[] => {
  // Get custom columns from all the rows in table.
  var customColumnKeys = new Set<string>();
  for (const row of rows) {
    if (!row.custom_fields) {
      continue;
    }
    const customFields: string[] = Object.keys(row.custom_fields);
    customFields.forEach((cf) => customColumnKeys.add(cf));
  }

  var finalColumns: ColumnDef<LeadRow>[] = [...baseLeadColumns];
  // Custom columns also has AI created fields like "evaluation" which are
  // populated whenever the lead is approved by the user.
  // Since we know the structure of this object, we will derive columns
  // from its keys separately.
  const evaluationKey = "evaluation";
  if (customColumnKeys.has(evaluationKey)) {
    const evaluationColumns: ColumnDef<LeadRow>[] = [
      {
        id: "fit_score",
        header: "Fit Score",
        accessorFn: (row) =>
          row.custom_fields ? row.custom_fields.evaluation.fit_score : null,
        meta: {
          displayName: "Fit Score",
          visibleInitially: true,
        } as CustomColumnMeta,
      },
      {
        id: "persona_match",
        header: "Persona Match",
        accessorFn: (row) =>
          row.custom_fields ? row.custom_fields.evaluation.persona_match : null,
        meta: {
          displayName: "Persona Match",
          visibleInitially: true,
        } as CustomColumnMeta,
      },
      {
        id: "matchin_criteria",
        header: "Matching Criteria",
        accessorFn: (row) =>
          row.custom_fields
            ? row.custom_fields.evaluation.matching_criteria
            : null,
        meta: {
          displayName: "Matching Criteria",
          visibleInitially: true,
        } as CustomColumnMeta,
      },
      {
        id: "recommended_approach",
        header: "Recommended Approach",
        accessorFn: (row) =>
          row.custom_fields
            ? row.custom_fields.evaluation.recommended_approach
            : null,
        meta: {
          displayName: "Recommended Approach",
          visibleInitially: true,
        } as CustomColumnMeta,
      },
      {
        id: "rationale",
        header: "Rationale",
        accessorFn: (row) =>
          row.custom_fields ? row.custom_fields.evaluation.rationale : null,
        meta: {
          displayName: "Rationale",
          visibleInitially: true,
        } as CustomColumnMeta,
      },
      {
        id: "analysis",
        header: "Analysis",
        accessorFn: (row) =>
          row.custom_fields ? row.custom_fields.evaluation.analysis : null,
        meta: {
          displayName: "Analysis",
          visibleInitially: true,
        } as CustomColumnMeta,
      },
    ];
    finalColumns.push(...evaluationColumns);

    // Delete the key so we don't create it again when creating the remaining
    // custom column keys.
    customColumnKeys.delete(evaluationKey);
  }

  customColumnKeys.forEach((columnKey) => {
    finalColumns.push({
      id: columnKey,
      accessorFn: (row) => row.custom_fields,
      header: getCustomColumnDisplayName(columnKey),
      cell: (info) => {
        // Render values in each cell for the given Custom Column.
        const customFields = info.getValue() as Record<string, any> | null;
        if (customFields && columnKey in customFields) {
          return customFields[columnKey];
        }
        return null;
      },
      minSize: 200,
      filterFn: "arrIncludesSome",
      meta: {
        displayName: getCustomColumnDisplayName(columnKey),
        visibleInitially: true,
      },
    });
  });
  return finalColumns;
};
