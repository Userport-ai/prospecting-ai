// UI for viewing Accounts uploaded by a user.
// export default function Accounts() {}

import { columns } from "./Columns";
import { DataTable } from "./DataTable";

function getData() {
  // Fetch data from your API here.
  return [
    {
      id: "728ed52f",
      name: "Stripe",
      linkedin_url: "https://www.linkedin.com/in/addarsh-chandrasekar",
      status: "pending",
      industry: "Software, AI, SaaS, FinTech",
    },
    {
      id: "72xed52f",
      name: "Google",
      status: "complete",
    },
    {
      id: "728edbb2f",
      name: "Rippling",
      status: "failed",
    },
    {
      id: "72oed52f",
      name: "Microsoft",
      linkedin_url: "https://www.linkedin.com/in/addarsh-chandrasekar",
      status: "complete",
      industry: "Software, AI, SaaS, FinTech",
    },
    {
      id: "72oed52f",
      name: "Dabur",
      status: "complete",
    },
    {
      id: "728ed52f",
      name: "Databricks",
      status: "pending",
    },
    {
      id: "72xed52f",
      name: "Snowflake",
      status: "complete",
    },
    {
      id: "728edbb2f",
      name: "Zuddl",
      status: "failed",
      industry: "Software, AI, SaaS, FinTech",
    },
    {
      id: "72oed52f",
      name: "Zomato",
      status: "complete",
    },
    {
      id: "72oed52f",
      name: "Salesforce",
      status: "complete",
    },
    {
      id: "728ed52f",
      name: "Postman",
      status: "pending",
    },
    {
      id: "72xed52f",
      name: "Uber",
      status: "complete",
    },
    {
      id: "728edbb2f",
      name: "Retool",
      status: "failed",
    },
    {
      id: "72oed52f",
      name: "Zendesk",
      status: "complete",
    },
    {
      id: "72oed52f",
      name: "Airbnb",
      status: "complete",
    },
    // ...
  ];
}

export default function Accounts() {
  const data = getData();

  return (
    <div className="w-11/12 mx-auto py-10">
      <DataTable columns={columns} data={data} />
    </div>
  );
}
