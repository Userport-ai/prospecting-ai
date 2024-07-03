import { Table } from "antd";

const columns = [
  {
    title: "Name",
    dataIndex: "name",
    key: "name",
    // render: (_, record) => <a href={record.url}>{record.name}</a>,
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
    render: (_, record) => <a href="/">View</a>,
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
    url: "www.linkedin.com",
  },
  {
    key: "1",
    name: "Jean-Denis Graze",
    roleTitle: "CTO",
    companyName: "Plaid",
    industry: "Financial Services, Payments",
    companyHeadcount: "1221",
    url: "www.linkedin.com",
  },
  {
    key: "2",
    name: "Marc Benioff",
    roleTitle: "CEO",
    companyName: "Salesforce",
    industry: "CRM, ERP, Marketing",
    companyHeadcount: "15,200",
    url: "www.linkedin.com",
  },
];

const LeadsTable = () => <Table columns={columns} dataSource={data} />;
export default LeadsTable;
