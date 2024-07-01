import { Table } from "antd";

const columns = [
  {
    title: "Name",
    dataIndex: "name",
    key: "name",
  },
  {
    title: "Role Title",
    dataIndex: "roleTitle",
    key: "roleTitle",
  },
  {
    title: "Company Name",
    dataIndex: "companyName",
    key: "companyName",
  },
  {
    title: "Industry",
    dataIndex: "industry",
    key: "industry",
  },
  {
    title: "Company Headcount",
    dataIndex: "companyHeadcount",
    key: "companyHeadcount",
  },
  {
    title: "Research results",
    dataIndex: "researchResults",
    key: "researchResults",
    render: (_, record) => <a href="/icp">View</a>,
  },
];

const data = [
  {
    key: "1",
    name: "John Smith",
    roleTitle: "CEO",
    companyName: "Hubspot",
    industry: "CRM, Marketing tech",
    companyHeadcount: "10,456",
    researchResultsUrl: "",
  },
  {
    key: "1",
    name: "Jean-Denis Graze",
    roleTitle: "CTO",
    companyName: "Plaid",
    industry: "Financial Services, Payments",
    companyHeadcount: "1221",
    researchResultsUrl: "",
  },
  {
    key: "2",
    name: "Marc Benioff",
    roleTitle: "CEO",
    companyName: "Salesforce",
    industry: "CRM, ERP, Marketing",
    companyHeadcount: "15,200",
    researchResultsUrl: "",
  },
];

const LeadsTable = () => <Table columns={columns} dataSource={data} />;
export default LeadsTable;
