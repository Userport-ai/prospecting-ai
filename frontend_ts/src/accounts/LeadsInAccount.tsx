import LeadsTable from "@/leads/LeadsTable";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import SuggestedLeads from "@/leads/SuggestedLeads";
import { useEffect, useState } from "react";
import { Separator } from "@/components/ui/separator";
import { useAuthContext } from "@/auth/AuthProvider";
import { Account, getAccount } from "@/services/Accounts";
import { useParams } from "react-router";
import ScreenLoader from "@/common/ScreenLoader";

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
      .then((account) => setAccount(account))
      .catch((error) =>
        setErrorMessage(`Failed to Get Account Details: ${String(error)}`)
      );
  }, []);

  // Handler once suggested leads are added by User.
  const onAddLeads = () => {
    // Switch tabs.
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
    "w-full text-gray-500 text-sm hover:text-gray-700 py-2 rounded-lg data-[state=active]:bg-gray-200  data-[state=active]:text-gray-700";

  return (
    <div className="px-4 mt-2">
      <h1 className="font-bold text-gray-700 text-3xl mb-4 w-fit">
        {account.name}
      </h1>
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
          <LeadsTable />
        </TabsContent>
        <TabsContent value={LeadViewTab.SUGGESTED_LEADS}>
          <SuggestedLeads accountId={account.id} onAddLeads={onAddLeads} />
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default LeadsInAccount;
