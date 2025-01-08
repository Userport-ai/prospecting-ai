import { useEffect, useState } from "react";
import {
  getCoreRowModel,
  useReactTable,
  getPaginationRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  ColumnDef,
  ColumnSort,
  ColumnFilter,
} from "@tanstack/react-table";
import AddCustomColumn, { CustomColumnInput } from "@/table/AddCustomColumn";
import CommonTable from "@/table/CommonTable";
import EnumFilter from "@/table/EnumFilter";
import VisibleColumns from "@/table/VisibleColumns";
import TextFilter from "@/table/TextFilter";
import { getLeadColumns } from "./Columns";
import { CustomColumnMeta } from "@/table/CustomColumnMeta";
import { Lead as LeadRow, listLeads } from "@/services/Leads";
import { useAuthContext } from "@/auth/AuthProvider";
import ScreenLoader from "@/common/ScreenLoader";
import { useParams } from "react-router";

const ZeroStateDisplay = () => {
  return (
    <div className="flex flex-col gap-2 items-center justify-center h-64 text-center bg-gray-50 border border-dashed border-gray-300 rounded-md p-6">
      <div className="text-gray-600 mb-4">
        <div className="text-xl font-semibold">No Data Available</div>
        <div className="text-sm">Start by adding Accounts to prospect.</div>
      </div>
    </div>
  );
};

interface TableProps {
  columns: ColumnDef<LeadRow>[];
  data: LeadRow[];
  onCustomColumnAdded: (arg0: CustomColumnInput) => void;
}

export const Table: React.FC<TableProps> = ({
  columns,
  data,
  onCustomColumnAdded,
}) => {
  const [sorting, setSorting] = useState<ColumnSort[]>([]);
  const [columnFilters, setColumnFilters] = useState<ColumnFilter[]>([]);
  const [rowSelection, setRowSelection] = useState({});
  const [pagination, setPagination] = useState({
    pageIndex: 0, //initial page index
    pageSize: 10, //default page size
  });

  var initialColumnVisibility: Record<string, boolean> = {};
  columns.forEach((col) => {
    if (!col.id) {
      return;
    }
    initialColumnVisibility[col.id] = false;
    if ((col.meta as CustomColumnMeta).visibleInitially === true) {
      initialColumnVisibility[col.id] = true;
    }
  });
  const [columnVisibility, setColumnVisibility] = useState(
    initialColumnVisibility
  );
  // Following https://tanstack.com/table/v8/docs/framework/react/examples/column-sizing for column resizing
  const columnResizeMode = "onChange";
  const columnResizeDirection = "ltr";

  const table = useReactTable({
    data,
    columns,
    columnResizeMode,
    columnResizeDirection,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onColumnVisibilityChange: setColumnVisibility,
    onRowSelectionChange: setRowSelection,
    onPaginationChange: setPagination,
    // Needed to solve this error: https://github.com/TanStack/table/issues/5026.
    autoResetPageIndex: false,
    state: {
      sorting,
      columnFilters,
      columnVisibility,
      rowSelection,
      pagination,
    },
  });

  if (data.length === 0) {
    // No accounts found.
    return <ZeroStateDisplay />;
  }

  const handleCustomColumnAdd = (customColumnInfo: CustomColumnInput) => {
    // Fetch the rows that need to be enriched. By default,
    // we fetch all the rows on the current page.
    const rowIds = table.getRowModel().rows.map((row) => row.original.id);
    customColumnInfo.rowIds = rowIds;
    onCustomColumnAdded(customColumnInfo);
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex gap-4">
        {/* Filter Controls */}
        <div className="flex gap-4">
          <TextFilter
            table={table}
            columnId={"name"}
            placeholder={"Filter Lead name..."}
          />

          {/* Status Filter */}
          <EnumFilter
            table={table}
            columnId={"enrichment_status"}
            columnFilters={columnFilters}
          />
        </div>

        {/* View visible Columns. */}
        <VisibleColumns table={table} />
      </div>

      <div className="flex mt-2 gap-6">
        {/* TODO: Add Leads to the table. */}

        {/* Add custom column */}
        <AddCustomColumn onAdded={handleCustomColumnAdd} />
      </div>

      {/* Table Container */}
      <CommonTable
        table={table}
        columns={columns}
        columnResizeMode={columnResizeMode}
        pagination={pagination}
      />
    </div>
  );
};

// Displays table with list of leads.
export default function LeadsTable() {
  const authContext = useAuthContext();
  const [leads, setLeads] = useState<LeadRow[]>([]);
  const [columns, setColumns] = useState<ColumnDef<LeadRow>[]>([]);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const { id } = useParams<{ id?: string }>();
  const accountId: string | null = id ? id : null;

  useEffect(() => {
    listLeads(authContext, accountId)
      .then((leads) => {
        setLeads(leads);
        setColumns(getLeadColumns(leads));
      })
      .catch((error) =>
        setError(new Error(`Failed to fetch Accounts: ${error.message}`))
      )
      .finally(() => setLoading(false));
  }, [authContext]);

  if (loading) {
    return <ScreenLoader />;
  }

  if (error) {
    throw error;
  }

  // Handler for when custom column inputs are provided by the user.
  const onCustomColumnAdded = (customColumnInfo: CustomColumnInput) => {
    // TODO: call server to send custom column request instead.
    console.log("custom colum info: ", customColumnInfo);
  };

  return (
    <div className="w-11/12 mx-auto py-2">
      <h1 className="font-bold text-gray-700 text-2xl mb-5">Leads</h1>
      <Table
        columns={columns}
        data={leads}
        onCustomColumnAdded={onCustomColumnAdded}
      />
    </div>
  );
}
