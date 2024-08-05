import "./leads-table.css";
import { Table, Typography } from "antd";

const { Text, Link } = Typography;

function renderLinkedInProfile(person_name, record, index) {
  const linkedin_url = record.person_linkedin_url;
  return (
    <Link href={linkedin_url} target="_blank">
      {person_name}
    </Link>
  );
}

function renderIndustries(industries, record, index) {
  return <Text>{industries.join(", ")}</Text>;
}

function renderResearchStatus(researchStatus, record, index) {
  const status = record.status === "complete" ? "Complete" : "In Progress";
  const link =
    record.status === "complete" ? "/lead-research-reports/" + record.id : "";
  return <Link href={link}>{status}</Link>;
}

const columns = [
  {
    title: "Name",
    dataIndex: "person_name",
    key: "person_name",
    render: renderLinkedInProfile,
  },
  {
    title: "Role Title",
    dataIndex: "person_role_title",
    key: "person_role_title",
  },
  {
    title: "Company Name",
    dataIndex: "company_name",
    key: "company_name",
  },
  {
    title: "Industries",
    dataIndex: "company_industry_categories",
    key: "company_industry_categories",
    render: renderIndustries,
  },
  {
    title: "Company Headcount",
    dataIndex: "company_headcount",
    key: "company_headcount",
  },
  {
    title: "Research Status",
    dataIndex: "researchResults",
    key: "researchResults",
    render: renderResearchStatus,
  },
];

// Mock data from server.
export const leadsResult = {
  status: "success",
  leads: [
    {
      id: "66ab9633a3bb9048bc1a0be5",
      creation_date: null,
      last_updated_date: null,
      person_linkedin_url: "https://www.linkedin.com/in/zperret",
      person_profile_id: null,
      company_profile_id: null,
      person_name: "Zachary Perret",
      company_name: "Plaid",
      person_role_title: "Co-Founder / CEO",
      status: "complete",
      company_headcount: 1222,
      company_industry_categories: [
        "banking",
        "finance",
        "financial-services",
        "fintech-e067",
        "insurtech",
        "software",
        "wealth-management",
      ],
      search_results_map: null,
      report_creation_date_readable_str: null,
      report_publish_cutoff_date: null,
      report_publish_cutoff_date_readable_str: null,
      details: null,
    },
  ],
};
function LeadsTable({ leads }) {
  return <Table id="leads-table" columns={columns} dataSource={leads} />;
}
export default LeadsTable;
