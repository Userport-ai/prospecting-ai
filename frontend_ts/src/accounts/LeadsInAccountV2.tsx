import LeadsTable from "@/leads/LeadsTable";
import { useEffect, useState } from "react";
import { useAuthContext } from "@/auth/AuthProvider";
import { Account, getAccount } from "@/services/Accounts";
import { Link, useParams } from "react-router";
import ScreenLoader from "@/common/ScreenLoader";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

// Display path to current view.
const PathToView: React.FC<{ account: Account }> = ({ account }) => {
  return (
    <Breadcrumb>
      <BreadcrumbList>
        <BreadcrumbItem>
          <BreadcrumbLink asChild>
            <Link to="/accounts" className="text-gray-500">
              {" "}
              Accounts
            </Link>
          </BreadcrumbLink>
        </BreadcrumbItem>
        <BreadcrumbSeparator />
        <BreadcrumbItem>
          <BreadcrumbPage className="font-medium">
            {account.name}
          </BreadcrumbPage>
        </BreadcrumbItem>
      </BreadcrumbList>
    </Breadcrumb>
  );
};

// Display Leads in a table and also the suggested
// leads as recommended by AI.
const LeadsInAccountV2 = () => {
  const authContext = useAuthContext();
  const [account, setAccount] = useState<Account | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>();

  // Account ID must exist in this route.
  const { id } = useParams<{ id?: string }>();
  const accountId: string = id!;

  useEffect(() => {
    getAccount(authContext, accountId)
      .then((account) => setAccount(account))
      .catch((error) =>
        setErrorMessage(`Failed to Get Account Details: ${String(error)}`)
      );
  }, []);

  if (errorMessage) {
    return (
      <div className="flex justify-center py-2">
        {" "}
        <p className="text-destructive font-semibold">{errorMessage}</p>
      </div>
    );
  }

  if (!account) {
    return <ScreenLoader />;
  }

  return (
    <div className="px-4 mt-2 flex flex-col gap-6">
      <PathToView account={account} />
      <h1 className="font-bold text-gray-700 text-3xl w-fit">{account.name}</h1>
      <LeadsTable accountId={accountId} />
    </div>
  );
};

export default LeadsInAccountV2;
