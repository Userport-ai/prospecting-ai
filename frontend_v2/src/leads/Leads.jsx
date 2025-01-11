import { useState } from "react";
import { leadsColumns } from "./Columns";
import { Table } from "./Table";

function getData() {
  // When there is no data.
  //   return [];

  return [
    {
      id: "72xed52f",
      name: "John Smith",
      company_name: "Google",
      duration_at_company: "2 months",
      status: "complete",
      role_title: "Senior Manager, Engineering",
      email: "john.smith@gmail.com",
      phone: "+16829975375",
    },
    {
      id: "72xed52x",
      name: "Jane Brown",
      company_name: "Stripe",
      duration_at_company: "1 year",
      status: "pending",
      role_title: "Vice President of Engineering",
      email: "jane.brown23@gmail.com",
      phone: "+16829975375",
    },
  ];
}

export default function Leads() {
  const [data, setData] = useState(getData());
  const [columns, setColumns] = useState(leadsColumns);

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
    <div className="w-11/12 mx-auto py-2">
      <h1 className="font-bold text-gray-700 text-2xl mb-5">Leads</h1>
      {data.length === 0 && (
        <div className="flex flex-col gap-2 items-center justify-center h-64 text-center bg-gray-50 border border-dashed border-gray-300 rounded-md p-6">
          <div className="text-gray-600 mb-4">
            <div className="text-xl font-semibold">No Data Available</div>
            <div className="text-sm">Start by adding Accounts to prospect.</div>
          </div>
        </div>
      )}
      {data.length > 0 && (
        <Table
          columns={columns}
          data={data}
          onCustomColumnAdded={onCustomColumnAdded}
        />
      )}
    </div>
  );
}
