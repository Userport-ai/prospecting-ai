import { ArrowUpDown, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";

export const columns = [
  {
    accessorKey: "name",
    header: "Name",
    size: 300,
  },
  {
    accessorKey: "status",
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
  },
  {
    accessorKey: "location",
    header: "HQ",
    size: 100,
  },
  {
    accessorKey: "employee_count",
    header: "Employee Count",
    size: 100,
  },
  {
    accessorKey: "customers",
    header: "Customers",
    size: 200,
  },
  {
    accessorKey: "technologies",
    header: "Technologies",
    size: 200,
  },
  {
    accessorKey: "competitors",
    header: "Competitors",
    size: 200,
  },
  {
    accessorKey: "industry",
    header: "Industry",
    size: 200,
  },
  {
    accessorKey: "website",
    header: "Website",
    size: 100,
  },
  {
    accessorKey: "linkedin_url",
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
  },
  {
    accessorKey: "company_type",
    header: "Type",
    size: 100,
  },
  {
    accessorKey: "created_at",
    header: "Created On",
    size: 100,
  },
  {
    accessorKey: "funding_details",
    header: "Funding Details",
    size: 100,
  },
  {
    accessorKey: "founded_year",
    header: "Founded Year",
    size: 100,
  },
];
