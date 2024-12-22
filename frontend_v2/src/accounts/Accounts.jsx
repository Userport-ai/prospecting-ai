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
