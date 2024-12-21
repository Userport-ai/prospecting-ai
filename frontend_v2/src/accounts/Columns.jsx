import { ArrowUpDown, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";

export const columns = [
  {
    accessorKey: "name",
    displayName: "Name",
    header: "Name",
    size: 300,
    visibleInitially: true,
  },
  {
    accessorKey: "status",
    displayName: "Status",
    header: ({ column }) => {
      return (
        <div className="flex items-center">
          Status
          <Button
            variant="ghost"
            className="hover:bg-transparent hover:text-white"
            onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
          >
            <ArrowUpDown className="ml-2" />
          </Button>
        </div>
      );
    },
    size: 100,
    // Reference: https://tanstack.com/table/v8/docs/guide/column-filtering.
    filterFn: "arrIncludesSome",
    visibleInitially: true,
  },
  {
    accessorKey: "location",
    displayName: "Location",
    header: "HQ",
    size: 100,
    visibleInitially: false,
  },
  {
    accessorKey: "employee_count",
    displayName: "Employee Count",
    header: "Employee Count",
    size: 100,
    visibleInitially: true,
  },
  {
    accessorKey: "customers",
    displayName: "Customers",
    header: "Customers",
    size: 200,
    visibleInitially: true,
  },
  {
    accessorKey: "technologies",
    displayName: "Technologies",
    header: "Technologies",
    size: 200,
    visibleInitially: true,
  },
  {
    accessorKey: "competitors",
    displayName: "Competitors",
    header: "Competitors",
    size: 200,
    visibleInitially: true,
  },
  {
    accessorKey: "industry",
    displayName: "Industry",
    header: "Industry",
    size: 200,
    visibleInitially: true,
  },
  {
    accessorKey: "website",
    displayName: "Website",
    header: "Website",
    size: 100,
    visibleInitially: false,
  },
  {
    accessorKey: "linkedin_url",
    displayName: "LinkedIn URL",
    header: "LinkedIn URL",
    size: 100,
    cell: ({ row }) => {
      const url = row.getValue("linkedin_url");
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
    visibleInitially: false,
  },
  {
    accessorKey: "company_type",
    displayName: "Company Type",
    header: "Type",
    size: 100,
    visibleInitially: false,
  },
  {
    accessorKey: "created_at",
    displayName: "Created On",
    header: "Created On",
    size: 100,
    visibleInitially: false,
  },
  {
    accessorKey: "funding_details",
    displayName: "Funding Details",
    header: "Funding Details",
    size: 100,
    visibleInitially: false,
  },
  {
    accessorKey: "founded_year",
    displayName: "Founded Year",
    header: "Founded Year",
    size: 100,
    visibleInitially: false,
  },
];
