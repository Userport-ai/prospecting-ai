import "./leads-table.css";
import { Table, Typography } from "antd";
import { useNavigate } from "react-router-dom";

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

function renderReportStatus(researchStatus, record, index) {
  var status = "In Progress";
  if (record.status === "complete") {
    return <Link className="research-report-ready">Ready</Link>;
  } else if (record.status === "failed_with_errors") {
    return <Text className="research-report-error">Error</Text>;
  }
  return <Text className="research-report-in-progress">{status}</Text>;
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
    title: "Report Status",
    dataIndex: "researchResults",
    key: "researchResults",
    render: renderReportStatus,
  },
];

function LeadsTable({ leads }) {
  const navigate = useNavigate();
  return (
    <>
      <Table
        id="leads-table"
        columns={columns}
        dataSource={leads}
        onRow={(record, index) => {
          return {
            onClick: (e) => {
              if (
                e.target.classList.contains("research-report-ready") === true
              ) {
                // Navigate to the Research Report link. This will prevent complete page load.
                return navigate("/lead-research-reports/" + record.id);
              }
            },
          };
        }}
      />
    </>
  );
}
export default LeadsTable;
