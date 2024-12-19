// UI for viewing Accounts uploaded by a user.
// export default function Accounts() {}

import { columns } from "./Columns";
import { DataTable } from "./DataTable";

function getData() {
  // Fetch data from your API here.
  return [
    {
      id: "728ed52f",
      amount: 100,
      status: "pending",
      email: "m@example.com",
    },
    {
      id: "72xed52f",
      amount: 200,
      status: "complete",
      email: "x@example.com",
    },
    {
      id: "728edbb2f",
      amount: 1005,
      status: "failed",
      email: "r@example.com",
    },
    {
      id: "72oed52f",
      amount: 200,
      status: "complete",
      email: "l@example.com",
    },
    {
      id: "72oed52f",
      amount: 200,
      status: "complete",
      email: "l@example.com",
    },
    {
      id: "728ed52f",
      amount: 100,
      status: "pending",
      email: "m@example.com",
    },
    {
      id: "72xed52f",
      amount: 200,
      status: "complete",
      email: "xNosra@example.com",
    },
    {
      id: "728edbb2f",
      amount: 1005,
      status: "failed",
      email: "r@example.com",
    },
    {
      id: "72oed52f",
      amount: 200,
      status: "complete",
      email: "l@example.com",
    },
    {
      id: "72oed52f",
      amount: 200,
      status: "complete",
      email: "l@example.com",
    },
    {
      id: "728ed52f",
      amount: 100,
      status: "pending",
      email: "m@example.com",
    },
    {
      id: "72xed52f",
      amount: 200,
      status: "complete",
      email: "xnosta@example.com",
    },
    {
      id: "728edbb2f",
      amount: 1005,
      status: "failed",
      email: "r@example.com",
    },
    {
      id: "72oed52f",
      amount: 200,
      status: "complete",
      email: "l@example.com",
    },
    {
      id: "72oed52f",
      amount: 200,
      status: "complete",
      email: "l@example.com",
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
