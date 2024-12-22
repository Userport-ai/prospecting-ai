import { useState } from "react";
import { accountColumns } from "./Columns";
import { DataTable } from "./DataTable";

function getData() {
  // Fetch data from your API here.
  return [
    {
      id: "728ed52f",
      name: "Stripe",
      linkedin_url: "https://www.linkedin.com/in/addarsh-chandrasekar",
      status: "pending",
      employee_count: 1000,
      customers: "Instacart, Doordash",
      technologies: "MongoDB, Postgres, Hubspot",
      competitors: "Paypal, Plaid",
      industry: "SaaS, FinTech",
    },
    {
      id: "72xed52f",
      name: "Google",
      customers: "CapitalOne, Shopify",
      employee_count: 100000,
      technologies: "Spanner, Bigquery",
      status: "complete",
      competitors: "OpenAI, Perplexity, Bing",
      industry: "Consumer, Cloud",
    },
    {
      id: "728edbb2f",
      name: "Rippling",
      status: "failed",
      employee_count: 2000,
      customers: "Mircosoft, Salesforce",
      technologies: "Hubspot, Stripe",
      competitors: "Workday, Gusto",
      industry: "SaaS, HR",
    },
    {
      id: "72oed52f",
      name: "Microsoft",
      linkedin_url: "https://www.linkedin.com/in/addarsh-chandrasekar",
      status: "complete",
      customers: "Boeing, JP Morgan",
      employee_count: 200000,
      technologies: "Apache Kafka",
      competitors: "Google, Salesforce",
      industry: "Enterprise Software, Cloud",
    },
    {
      id: "72oed52f",
      name: "Dabur",
      customers: "Consumers",
      status: "complete",
      technologies: "Google Analytics",
      employee_count: 10000,
      competitors: "Nestle, Himalaya",
      industry: "Consumer Goods",
    },
    {
      id: "728ed52f",
      name: "Databricks",
      customers: "Microsoft, Goldman Sachs",
      status: "pending",
      technologies: "Stripe, Postgres",
      employee_count: 5000,
      competitors: "Snowflake, Redshift",
      industry: "SaaS, Data Warehouse",
    },
    {
      id: "72xed52f",
      name: "Snowflake",
      customers: "Blackrock, Stripe",
      status: "complete",
      technologies: "Postgres, Salesforce",
      employee_count: 7000,
      competitors: "Databricks, Redshift",
      industry: "SaaS, Data Warehouse",
    },
    {
      id: "728edbb2f",
      name: "Zuddl",
      status: "failed",
      customers: "Postman",
      employee_count: 120,
      technologies: "Stripe, Clay",
      competitors: "cvent, Goldcast",
      industry: "SaaS, Event Marketing",
    },
    {
      id: "72oed52f",
      name: "Zomato",
      customers: "Consumer",
      employee_count: 2000,
      technologies: "Razorpay, Google Workspace",
      status: "complete",
      competitors: "Swiggy, Zepto",
      industry: "Consumer, Delivery",
    },
    {
      id: "72oed52f",
      name: "Salesforce",
      customers: "Zuddle, Pepper Content",
      employee_count: 10000,
      technologies: "Stripe, MongoDB",
      status: "complete",
      competitors: "Hubspot",
      industry: "SaaS, CRM",
    },
    {
      id: "728ed52f",
      name: "Postman",
      customers: "Twilio, Plaid",
      employee_count: 800,
      technologies: "Gong, Hubspot",
      status: "pending",
      competitors: "RapidAPI",
      industry: "SaaS, API testing",
    },
    {
      id: "72xed52f",
      name: "Uber",
      customers: "Consumers",
      employee_count: 10000,
      technologies: "Stripe, Glean",
      status: "complete",
      competitors: "Lyft, Grab",
      industry: "Consumer, Ride Hailing",
    },
    {
      id: "728edbb2f",
      name: "Retool",
      customers: "Doordash, Pepper Content",
      employee_count: 500,
      technologies: "Glean, Hubspot",
      status: "failed",
      competitors: "Vercel",
      industry: "SaaS, Internal Tools",
    },
    {
      id: "72oed52f",
      name: "Zendesk",
      customers: "Cisco",
      employee_count: 2000,
      technologies: "Postgres, Salesforce",
      status: "complete",
      competitors: "Freshworks",
      industry: "SaaS, Customer Support",
    },
    {
      id: "72oed52f",
      name: "Airbnb",
      customers: "Consumers",
      employee_count: 4000,
      technologies: "Google Analytics, React",
      competitors: "Booking.com, Marriot",
      status: "complete",
      industry: "Consumer, Short term Rental Marketplace",
    },
    // ...
  ];
}

export default function Accounts() {
  const [data, setData] = useState(getData());
  const [columns, setColumns] = useState(accountColumns);

  // Handler for when custom column inputs are provided by the user.
  const onCustomColumnAdded = (customColumnInfo) => {
    // TODO: call server to send custom column request instead
    // of manually updating the columns and rows in the table.
    const customColumnAccessorKey = "custom_column";
    setColumns([
      ...columns,
      {
        accessorKey: customColumnAccessorKey,
        displayName: customColumnInfo.columnName,
        header: customColumnInfo.columnName,
        size: 100,
        filterFn: "arrIncludesSome",
        visibleInitially: true,
      },
    ]);
    // Update columns for given RowIds with added column value.
    const rowIds = customColumnInfo.rowIds;
    var newData = [...data];
    newData.forEach((row) => {
      if (rowIds.includes(row.id)) {
        row[customColumnAccessorKey] = "pending";
      }
    });
    setData(newData);
  };

  return (
    <div className="w-11/12 mx-auto py-10">
      <DataTable
        columns={columns}
        data={data}
        onCustomColumnAdded={onCustomColumnAdded}
      />
    </div>
  );
}
