import LeadsTable from "@/leads/LeadsTable";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import SuggestedLeads from "@/leads/SuggestedLeads";
import { useEffect, useState } from "react";
import { Separator } from "@/components/ui/separator";
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
import { listLeads } from "@/services/Leads";

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

enum LeadViewTab {
  LEADS = "leads",
  SUGGESTED_LEADS = "suggested_leads",
}

// Display Leads in a table and also the suggested
// leads as recommended by AI.
const LeadsInAccount = () => {
  const authContext = useAuthContext();
  const [account, setAccount] = useState<Account | null>(null);
  const [activeTab, setActiveTab] = useState<string>(LeadViewTab.LEADS);
  const [errorMessage, setErrorMessage] = useState<string | null>();

  // Account ID must exist in this route.
  const { id } = useParams<{ id?: string }>();
  const accountId: string = id!;

  useEffect(() => {
    getAccount(authContext, accountId)
      .then((account) => {
        listLeads(authContext, accountId)
          .then((leads) => {
            setActiveTab(
              leads.length > 0 ? LeadViewTab.LEADS : LeadViewTab.SUGGESTED_LEADS
            );
            setAccount(account);
          })
          .catch((error) =>
            setErrorMessage(`Failed to list Leads: ${String(error)}`)
          );
      })
      .catch((error) =>
        setErrorMessage(`Failed to Get Account Details: ${String(error)}`)
      );
  }, []);

  // Handler once suggested leads are added by User.
  const onAddLeads = () => {
    // Switch tabs.
    console.log("got called");
    setActiveTab(LeadViewTab.LEADS);
  };

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

  const tabTriggerClass =
    "w-full text-gray-500 text-sm hover:text-gray-700 py-2 rounded-lg data-[state=active]:bg-purple-100  data-[state=active]:text-gray-700";

  return (
    <div className="px-4 mt-2 flex flex-col gap-6">
      <PathToView account={account} />
      <h1 className="font-bold text-gray-700 text-3xl w-fit">{account.name}</h1>
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="w-[30rem] h-fit bg-transparent">
          <TabsTrigger value={LeadViewTab.LEADS} className={tabTriggerClass}>
            Leads
          </TabsTrigger>
          <TabsTrigger
            value={LeadViewTab.SUGGESTED_LEADS}
            className={tabTriggerClass}
          >
            AI Suggestions
          </TabsTrigger>
        </TabsList>

        <Separator className="mb-6 bg-gray-300" />

        <TabsContent value={LeadViewTab.LEADS}>
          <LeadsTable accountId={accountId} />
        </TabsContent>
        <TabsContent value={LeadViewTab.SUGGESTED_LEADS}>
          <SuggestedLeads accountId={account.id} onAddLeads={onAddLeads} />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default LeadsInAccount;
