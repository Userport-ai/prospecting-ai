import "./leads-table.css";
import { Table, Typography } from "antd";
import { usePostHog } from "posthog-js/react";

const { Text, Link } = Typography;

// Returns empty state of Table when there are no rows.
function TableEmptyState() {
  return (
    <div id="leads-table-empty-container">
      <h2>No leads added</h2>
      <Text className="instructions-text">
        Leads are the prospects who you want to target in your outreach
        campaigns.
      </Text>
      <Text className="instructions-text">
        Once you add a new lead, AI will automatically research and fetch public
        information about the lead or their company.
      </Text>
      <Text className="instructions-text">
        AI will also automatically select the template matching the leads's
        persona and created personalized emails for you.
      </Text>
    </div>
  );
}

function renderLinkedInProfile(person_name, record, index) {
  // LinkedIn URL should always exist because it was originally provided as input by the user.
  const linkedin_url = record.person_linkedin_url;

  // If fetching of the Person's profile failed in the backend, person name will be null.
  const displayName = person_name ? person_name : linkedin_url;
  return (
    <Link href={linkedin_url} target="_blank">
      {displayName}
    </Link>
  );
}

function renderIndustries(industries, record, index) {
  if (industries === null) {
    return <Text></Text>;
  }
  return <Text>{industries.join(", ")}</Text>;
}

function renderReportStatus(researchStatus, record, index) {
  var status = "In Progress";
  if (record.status === "complete") {
    return (
      <Link
        className="research-report-ready"
        href={`/lead-research-reports/${record.id}`}
        target="_blank"
      >
        {" "}
        Ready
      </Link>
    );
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
  // Uncomment this once we start to return Categories once again (when there is a customer need)
  // Right now its costing 1 extra credit by Proxycurl so too expensive.
  // {
  //   title: "Industries",
  //   dataIndex: "company_industry_categories",
  //   key: "company_industry_categories",
  //   render: renderIndustries,
  // },
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
  const posthog = usePostHog();

  // Handle user click of a report on a givent able row.
  const handleTableRowClick = (record) => {
    return (e) => {
      if (e.target.classList.contains("research-report-ready") === true) {
        // Send Event.
        posthog.capture("report_ready_link_clicked", {
          report_id: record.id,
        });
      }
    };
  };

  return (
    <>
      <Table
        id="leads-table"
        columns={columns}
        dataSource={leads}
        locale={{
          emptyText: <TableEmptyState />,
        }}
        onRow={(record, index) => {
          return {
            onClick: handleTableRowClick(record),
          };
        }}
      />
    </>
  );
}
export default LeadsTable;
