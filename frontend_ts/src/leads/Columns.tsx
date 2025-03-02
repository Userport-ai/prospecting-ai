import { ChevronsUpDown } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import SortingDropdown from "../table/SortingDropdown";
import { CustomColumnMeta } from "@/table/CustomColumnMeta";
import { ColumnDef, Table } from "@tanstack/react-table";
import {
  AreaOfInterest,
  Lead as LeadRow,
  PersonalityTrait,
  PersonalizationSignal,
  RecommendedApproach,
} from "@/services/Leads";
import { formatDate } from "@/common/utils";
import { getCustomColumnDisplayName } from "@/table/AddCustomColumn";
import CellListView from "@/table/CellListView";
import RecommendedApproachView from "./RecommendedApproachView";
import AreasOfInterestView from "./AreasOfInterestView";
import PersonalityTraitsView from "./PersonalityTraitsView";
import PersonalizationSignalsView from "./PersonalizationSignalsView";

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
  var customColumnKeys = new Set<string>();
  for (const row of rows) {
    if (!row.custom_fields) {
      continue;
    }
    const customFields: string[] = Object.keys(row.custom_fields);
    customFields.forEach((cf) => customColumnKeys.add(cf));
  }

  // Helper to fetch matching signals for each lead.
  const getMatchingSignals = (lead: LeadRow): string[] | null => {
    if (!lead.custom_fields || !lead.custom_fields.evaluation) {
      return null;
    }
    const matchingCriteria = lead.custom_fields.evaluation.matching_criteria;
    const matchingSignals = lead.custom_fields.evaluation.matching_signals;
    if (matchingSignals) {
      return matchingSignals;
    } else if (matchingCriteria) {
      return matchingCriteria;
    }
    return null;
  };

  var finalColumns: ColumnDef<LeadRow>[] = [...baseLeadColumns];
  // Custom columns also has AI created fields like "evaluation" which are
  // populated whenever the lead is suggested or approved by the user.
  // Since we know the structure of this object, we will derive columns
  // from its keys separately.
  const evaluationKey = "evaluation";
  if (customColumnKeys.has(evaluationKey)) {
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
            row.custom_fields.evaluation.persona_match
          ) {
            return getCustomColumnDisplayName(
              row.custom_fields.evaluation.persona_match
            );
          }
          return null;
        },
        meta: {
          displayName: "Persona Match",
          visibleInitially: true,
        } as CustomColumnMeta,
      },
      {
        id: "rationale",
        header: "Rationale",
        minSize: 300,
        accessorFn: (row) =>
          row.custom_fields ? row.custom_fields.evaluation.rationale : null,
        meta: {
          displayName: "Rationale",
          visibleInitially: true,
          cellExpandable: true,
        } as CustomColumnMeta,
      },
      {
        id: "matching_signals",
        header: "Matching Criteria",
        minSize: 300,
        accessorFn: (row) => getMatchingSignals(row),
        cell: (info) => {
          const matchingSignals = info.getValue() as string[] | null;
          if (!matchingSignals) {
            return null;
          }
          return <CellListView values={matchingSignals} />;
        },
        meta: {
          displayName: "Matching Criteria",
          visibleInitially: true,
          cellExpandable: true,
        } as CustomColumnMeta,
      },
      {
        id: "analysis",
        header: "Analysis",
        minSize: 200,
        accessorFn: (row) =>
          row.custom_fields
            ? row.custom_fields.evaluation.overall_analysis
            : null,
        meta: {
          displayName: "Analysis",
          visibleInitially: false,
          cellExpandable: true,
        } as CustomColumnMeta,
      },
    ];
    finalColumns.push(...evaluationColumns);

    // Delete the key so we don't create it again when creating the remaining
    // custom column keys.
    customColumnKeys.delete(evaluationKey);
  }

  const personalityInsightsKey = "personality_insights";
  if (customColumnKeys.has(personalityInsightsKey)) {
    const personalityInsightsColumns: ColumnDef<LeadRow>[] = [
      {
        id: "traits",
        header: "Personality Traits",
        accessorFn: (row) =>
          row.custom_fields?.personality_insights?.traits ?? null,
        cell: (info) => {
          const personalityTraits = info.getValue() as PersonalityTrait | null;
          if (!personalityTraits) {
            return null;
          }
          // return JSON.stringify(info.getValue());
          return <PersonalityTraitsView personalityTrait={personalityTraits} />;
        },
        meta: {
          displayName: "Personality Traits",
          visibleInitially: false,
          cellExpandable: true,
        } as CustomColumnMeta,
      },
      {
        id: "engaged_products",
        header: "Products Engaged",
        accessorFn: (row) =>
          row.custom_fields?.personality_insights?.engaged_products ?? null,
        cell: (info) => {
          const engagedProducts = info.getValue() as string[] | null;
          if (!engagedProducts) {
            return null;
          }
          return <CellListView values={engagedProducts} />;
        },
        meta: {
          displayName: "Products Engaged",
          visibleInitially: false,
          cellExpandable: true,
        } as CustomColumnMeta,
      },
      {
        id: "areas_of_interest",
        header: "Areas of Interest",
        accessorFn: (row) =>
          row.custom_fields?.personality_insights?.areas_of_interest ?? null,
        cell: (info) => {
          const areasOfInterest = info.getValue() as AreaOfInterest[] | null;
          if (!areasOfInterest) {
            return null;
          }
          return <AreasOfInterestView areasOfInterest={areasOfInterest} />;
        },
        meta: {
          displayName: "Areas of Interest",
          visibleInitially: false,
          cellExpandable: true,
        } as CustomColumnMeta,
      },
      {
        id: "engaged_colleagues",
        header: "Engagement with Colleagues",
        accessorFn: (row) =>
          row.custom_fields?.personality_insights?.engaged_colleagues ?? null,
        cell: (info) => {
          const engagedColleagues = info.getValue() as string[] | null;
          if (!engagedColleagues) {
            return null;
          }
          return <CellListView values={engagedColleagues} />;
        },
        meta: {
          displayName: "Engagement with Colleagues",
          visibleInitially: false,
          cellExpandable: true,
        } as CustomColumnMeta,
      },
      {
        id: "recommended_approach",
        header: "Recommeded Approach",
        accessorFn: (row) =>
          row.custom_fields?.personality_insights?.recommended_approach ?? null,
        cell: (info) => {
          const recommendedApproach =
            info.getValue() as RecommendedApproach | null;
          if (!recommendedApproach) {
            return null;
          }
          return (
            <RecommendedApproachView
              recommendedApproach={recommendedApproach}
            />
          );
        },
        meta: {
          displayName: "Recommended Approach",
          visibleInitially: false,
          cellExpandable: true,
        } as CustomColumnMeta,
      },
      {
        id: "personalization_signals",
        header: "Personalization Signals",
        accessorFn: (row) =>
          row.custom_fields?.personality_insights?.personalization_signals ??
          null,
        cell: (info) => {
          const personalizationSignals = info.getValue() as
            | PersonalizationSignal[]
            | null;
          if (!personalizationSignals) {
            return null;
          }
          return (
            <PersonalizationSignalsView
              personalizationSignals={personalizationSignals}
            />
          );
        },
        meta: {
          displayName: "Recommended Approach",
          visibleInitially: false,
          cellExpandable: true,
        } as CustomColumnMeta,
      },
    ];
    finalColumns.push(...personalityInsightsColumns);

    // Delete the key so we don't create it again when creating the remaining
    // custom column keys.
    customColumnKeys.delete(personalityInsightsKey);
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
