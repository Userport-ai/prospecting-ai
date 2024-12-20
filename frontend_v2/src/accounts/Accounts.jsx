// UI for viewing Accounts uploaded by a user.
// export default function Accounts() {}

import { columns } from "./Columns";
import { DataTable } from "./DataTable";

function getData() {
  // Fetch data from your API here.
  return [
    {
      id: "728ed52f",
      name: "Addarsh Chandrasekar Anantharaman",
      linkedin_url: "https://www.linkedin.com/in/addarsh-chandrasekar",
      status: "pending",
      industry: "Software, AI, SaaS, FinTech",
    },
    {
      id: "72xed52f",
      name: "Addarsh Chandrasekar Anantharaman",
      status: "complete",
    },
    {
      id: "728edbb2f",
      name: "Addarsh Chandrasekar Anantharaman",
      status: "failed",
    },
    {
      id: "72oed52f",
      name: "Addarsh Chandrasekar Anantharaman",
      linkedin_url: "https://www.linkedin.com/in/addarsh-chandrasekar",
      status: "complete",
      industry: "Software, AI, SaaS, FinTech",
    },
    {
      id: "72oed52f",
      name: "Addarsh Chandrasekar Anantharaman",
      status: "complete",
    },
    {
      id: "728ed52f",
      status: "pending",
    },
    {
      id: "72xed52f",
      status: "complete",
    },
    {
      id: "728edbb2f",
      name: "Addarsh Chandrasekar Anantharaman",
      status: "failed",
      industry: "Software, AI, SaaS, FinTech",
    },
    {
      id: "72oed52f",
      status: "complete",
    },
    {
      id: "72oed52f",
      status: "complete",
    },
    {
      id: "728ed52f",
      status: "pending",
    },
    {
      id: "72xed52f",
      status: "complete",
    },
    {
      id: "728edbb2f",
      status: "failed",
    },
    {
      id: "72oed52f",
      status: "complete",
    },
    {
      id: "72oed52f",
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
